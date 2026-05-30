# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
# 	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the ECS CapacityProvider API.
"""

import pytest
import time
import logging
import boto3

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s

from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_ecs_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e.bootstrap_resources import get_bootstrap_resources
from e2e.tests.helper import ECSValidator
from e2e.tests.test_cluster import simple_cluster
from e2e.tests.test_task_definition import simple_task_definitions

RESOURCE_PLURAL = "capacityproviders"
SERVICE_RESOURCE_PLURAL = "services"

CREATE_WAIT_AFTER_SECONDS = 60
UPDATE_WAIT_AFTER_SECONDS = 60
DELETE_WAIT_AFTER_SECONDS = 60


def _create_test_asg(name_suffix: str) -> tuple:
    """Create a unique ASG for a capacity provider test. Returns (asg_arn, asg_name, lt_name)."""
    asg_client = boto3.client("autoscaling")
    ec2_client = boto3.client("ec2")

    asg_name = f"ack-ecs-cp-{name_suffix}"
    lt_name = f"ack-ecs-cp-lt-{name_suffix}"

    # Get default VPC subnets
    vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    vpc_id = vpcs["Vpcs"][0]["VpcId"]
    subnets = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    subnet_ids = [s["SubnetId"] for s in subnets["Subnets"][:2]]

    # Create launch template
    lt_resp = ec2_client.create_launch_template(
        LaunchTemplateName=lt_name,
        LaunchTemplateData={
            "ImageId": "resolve:ssm:/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id",
            "InstanceType": "t3.micro",
        },
    )
    lt_id = lt_resp["LaunchTemplate"]["LaunchTemplateId"]

    # Create ASG
    asg_client.create_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        LaunchTemplate={"LaunchTemplateId": lt_id, "Version": "$Latest"},
        MinSize=0,
        MaxSize=2,
        DesiredCapacity=0,
        VPCZoneIdentifier=",".join(subnet_ids),
        NewInstancesProtectedFromScaleIn=True,
    )

    resp = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    asg_arn = resp["AutoScalingGroups"][0]["AutoScalingGroupARN"]
    return asg_arn, asg_name, lt_name


def _delete_test_asg(asg_name: str, lt_name: str):
    """Clean up a test ASG and its launch template."""
    try:
        boto3.client("autoscaling").delete_auto_scaling_group(
            AutoScalingGroupName=asg_name, ForceDelete=True
        )
    except Exception:
        pass
    try:
        boto3.client("ec2").delete_launch_template(LaunchTemplateName=lt_name)
    except Exception:
        pass


@pytest.fixture(scope="module")
def simple_capacity_provider(ecs_client):
    resource_name = random_suffix_name("ack-ecs-cp", 24)

    # Each test gets its own ASG (AWS allows only one CP per ASG)
    suffix = resource_name.split("-")[-1]
    asg_arn, asg_name, lt_name = _create_test_asg(suffix)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["CAPACITY_PROVIDER_NAME"] = resource_name
    replacements["ASG_ARN"] = asg_arn

    resource_data = load_ecs_resource(
        "capacity_provider",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)

    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr, resource_name)

    try:
        _, deleted = k8s.delete_custom_resource(
            ref,
            period_length=DELETE_WAIT_AFTER_SECONDS,
        )
        assert deleted

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        validator = ECSValidator(ecs_client)
        cp = validator.get_capacity_provider(resource_name)
        # After deletion, capacity provider transitions to INACTIVE
        assert cp is None or cp.get("status") == "INACTIVE"
    finally:
        _delete_test_asg(asg_name, lt_name)


@service_marker
@pytest.mark.canary
class TestCapacityProvider:
    def test_create_delete(self, ecs_client, simple_capacity_provider):
        (ref, cr, cp_name) = simple_capacity_provider

        # Check CR for terminal condition (error)
        cr = k8s.get_resource(ref)
        assert cr is not None, "CR not found"
        terminal_condition = k8s.get_resource_condition(ref, "ACK.Terminal")
        assert terminal_condition is None or terminal_condition.get("status") != "True", \
            f"Terminal condition set: {terminal_condition}"

        validator = ECSValidator(ecs_client)
        assert validator.capacity_provider_exists(cp_name), \
            f"CapacityProvider {cp_name} not found in AWS. CR status: {cr.get('status', {})}"

        # Verify AWS API state
        cp = validator.get_capacity_provider(cp_name)
        assert cp["name"] == cp_name
        assert cp["status"] == "ACTIVE"
        assert cp["autoScalingGroupProvider"]["managedScaling"]["status"] == "ENABLED"
        assert cp["autoScalingGroupProvider"]["managedScaling"]["targetCapacity"] == 80

        # Verify CR status
        cr = k8s.get_resource(ref)
        assert cr["status"].get("status") == "ACTIVE"

        # Verify Synced condition
        assert k8s.get_resource_condition(ref, "ACK.ResourceSynced") is not None

    def test_update_managed_scaling(self, ecs_client, simple_capacity_provider):
        (ref, _, cp_name) = simple_capacity_provider

        # Update managedScaling targetCapacity
        updates = {
            "spec": {
                "autoScalingGroupProvider": {
                    "managedScaling": {
                        "status": "ENABLED",
                        "targetCapacity": 90,
                        "minimumScalingStepSize": 1,
                        "maximumScalingStepSize": 10,
                    },
                    "managedTerminationProtection": "DISABLED",
                },
            },
        }
        k8s.patch_custom_resource(ref, updates)
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)

        # Verify via AWS API
        validator = ECSValidator(ecs_client)
        cp = validator.get_capacity_provider(cp_name)
        assert cp["autoScalingGroupProvider"]["managedScaling"]["targetCapacity"] == 90
        assert cp["autoScalingGroupProvider"]["managedScaling"]["maximumScalingStepSize"] == 10

        # Verify Synced condition after update
        assert k8s.get_resource_condition(ref, "ACK.ResourceSynced") is not None


@pytest.fixture(scope="module")
def service_with_capacity_provider(
    ecs_client, simple_capacity_provider, simple_cluster, simple_task_definitions
):
    (_, _, cp_name) = simple_capacity_provider
    (_, _, cluster_name) = simple_cluster
    (_, _, task_def_name) = simple_task_definitions

    resource_name = random_suffix_name("ecs-svc-cp", 24)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["SERVICE_NAME"] = resource_name
    replacements["CLUSTER_NAME"] = cluster_name
    replacements["TASK_DEFINITION_NAME"] = task_def_name
    replacements["CAPACITY_PROVIDER_NAME"] = cp_name

    resource_data = load_ecs_resource(
        "service_with_capacity_provider",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, SERVICE_RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)

    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr, cluster_name, resource_name, cp_name)

    _, deleted = k8s.delete_custom_resource(
        ref,
        period_length=DELETE_WAIT_AFTER_SECONDS,
    )
    assert deleted


@service_marker
class TestCapacityProviderWithService:
    def test_service_uses_capacity_provider_strategy(
        self, ecs_client, service_with_capacity_provider
    ):
        (ref, _, cluster_name, service_name, cp_name) = service_with_capacity_provider

        validator = ECSValidator(ecs_client)
        resp = validator.get_service(cluster_name, service_name)
        assert resp is not None

        svc = resp["services"][0]
        assert svc["status"] == "ACTIVE"

        # Verify capacityProviderStrategy via AWS API
        cps = svc.get("capacityProviderStrategy", [])
        assert len(cps) == 1
        assert cps[0]["capacityProvider"] == cp_name
        assert cps[0]["weight"] == 1
        assert cps[0]["base"] == 0

        # Verify no launchType set (mutually exclusive with capacityProviderStrategy)
        assert svc.get("launchType", "") == ""

        # Verify Synced condition on Service CR
        assert k8s.get_resource_condition(ref, "ACK.ResourceSynced") is not None


@pytest.fixture(scope="module")
def managed_instances_cluster(ecs_client):
    """Create a dedicated cluster for managed instances capacity provider tests."""
    resource_name = random_suffix_name("ack-ecs-mi", 24)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["CLUSTER_NAME"] = resource_name

    resource_data = load_ecs_resource(
        "cluster",
        additional_replacements=replacements,
    )

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, "clusters",
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)

    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.wait_resource_consumed_by_controller(ref)
    assert cr is not None

    yield (ref, cr, resource_name)

    _, deleted = k8s.delete_custom_resource(
        ref,
        period_length=DELETE_WAIT_AFTER_SECONDS,
    )
    assert deleted


@pytest.fixture(scope="module")
def managed_instances_capacity_provider(ecs_client, managed_instances_cluster):
    (_, _, cluster_name) = managed_instances_cluster

    resource_name = random_suffix_name("ack-ecs-mi-cp", 24)
    bootstrap_resources = get_bootstrap_resources()

    replacements = REPLACEMENT_VALUES.copy()
    replacements["CAPACITY_PROVIDER_NAME"] = resource_name
    replacements["CLUSTER_NAME"] = cluster_name
    replacements["INFRA_ROLE_ARN"] = bootstrap_resources.ManagedInstancesInfraRole.arn

    resource_data = load_ecs_resource(
        "capacity_provider_managed_instances",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)

    time.sleep(60)  # Managed instances CPs take longer to provision
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr, resource_name, cluster_name)

    _, deleted = k8s.delete_custom_resource(
        ref,
        period_length=DELETE_WAIT_AFTER_SECONDS,
    )
    assert deleted

    time.sleep(DELETE_WAIT_AFTER_SECONDS)


@service_marker
@pytest.mark.slow
class TestManagedInstancesCapacityProvider:
    def test_create_managed_instances(self, ecs_client, managed_instances_capacity_provider):
        (ref, _, cp_name, cluster_name) = managed_instances_capacity_provider

        validator = ECSValidator(ecs_client)
        cp = validator.get_capacity_provider(cp_name)
        assert cp is not None
        assert cp["name"] == cp_name
        assert cp["status"] == "ACTIVE"
        assert cp.get("cluster") is not None

        # Verify managedInstancesProvider via AWS API
        mip = cp.get("managedInstancesProvider")
        assert mip is not None
        assert mip.get("infrastructureRoleArn") is not None
        assert mip["infrastructureOptimization"]["scaleInAfter"] == 15

        # Verify Synced condition
        assert k8s.get_resource_condition(ref, "ACK.ResourceSynced") is not None

    def test_update_managed_instances(self, ecs_client, managed_instances_capacity_provider):
        (ref, _, cp_name, _) = managed_instances_capacity_provider

        # Update scaleInAfter
        updates = {
            "spec": {
                "managedInstancesProvider": {
                    "infrastructureOptimization": {
                        "scaleInAfter": 30,
                    },
                },
            },
        }
        k8s.patch_custom_resource(ref, updates)
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)

        # Verify via AWS API
        validator = ECSValidator(ecs_client)
        cp = validator.get_capacity_provider(cp_name)
        assert cp["managedInstancesProvider"]["infrastructureOptimization"]["scaleInAfter"] == 30

        # Verify Synced condition after update
        assert k8s.get_resource_condition(ref, "ACK.ResourceSynced") is not None


@pytest.fixture(scope="module")
def cluster_with_capacity_providers(ecs_client, simple_capacity_provider):
    """Create a cluster that uses a capacity provider in its default strategy."""
    (_, _, cp_name) = simple_capacity_provider

    resource_name = random_suffix_name("ack-ecs-cl-cp", 24)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["CLUSTER_NAME"] = resource_name
    replacements["CAPACITY_PROVIDER_NAME"] = cp_name

    resource_data = load_ecs_resource(
        "cluster_with_capacity_providers",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, "clusters",
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)

    time.sleep(CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr, resource_name, cp_name)

    _, deleted = k8s.delete_custom_resource(
        ref,
        period_length=DELETE_WAIT_AFTER_SECONDS,
    )
    assert deleted


@service_marker
class TestClusterWithCapacityProviders:
    def test_cluster_default_capacity_provider_strategy(
        self, ecs_client, cluster_with_capacity_providers
    ):
        (ref, _, cluster_name, cp_name) = cluster_with_capacity_providers

        validator = ECSValidator(ecs_client)
        resp = validator.get_cluster(cluster_name)
        assert resp is not None

        cluster = resp["clusters"][0]
        assert cluster["status"] == "ACTIVE"

        # Verify capacityProviders via AWS API
        assert cp_name in cluster.get("capacityProviders", [])

        # Verify defaultCapacityProviderStrategy
        strategy = cluster.get("defaultCapacityProviderStrategy", [])
        assert len(strategy) >= 1
        assert strategy[0]["capacityProvider"] == cp_name
        assert strategy[0]["weight"] == 1
        assert strategy[0]["base"] == 0

        # Verify Synced condition
        assert k8s.get_resource_condition(ref, "ACK.ResourceSynced") is not None

    def test_update_cluster_capacity_provider_strategy(
        self, ecs_client, cluster_with_capacity_providers
    ):
        (ref, _, cluster_name, cp_name) = cluster_with_capacity_providers

        # Update the default strategy weight
        updates = {
            "spec": {
                "defaultCapacityProviderStrategy": [
                    {
                        "capacityProvider": cp_name,
                        "weight": 2,
                        "base": 1,
                    },
                ],
            },
        }
        k8s.patch_custom_resource(ref, updates)
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)

        # Verify via AWS API
        validator = ECSValidator(ecs_client)
        resp = validator.get_cluster(cluster_name)
        cluster = resp["clusters"][0]

        strategy = cluster.get("defaultCapacityProviderStrategy", [])
        assert len(strategy) >= 1
        assert strategy[0]["capacityProvider"] == cp_name
        assert strategy[0]["weight"] == 2
        assert strategy[0]["base"] == 1

        # Verify Synced condition after update
        assert k8s.get_resource_condition(ref, "ACK.ResourceSynced") is not None
