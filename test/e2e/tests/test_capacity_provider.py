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

RESOURCE_PLURAL = "capacityproviders"

CREATE_WAIT_AFTER_SECONDS = 60
UPDATE_WAIT_AFTER_SECONDS = 60
DELETE_WAIT_AFTER_SECONDS = 60


@pytest.fixture(scope="module")
def launch_template_for_capacity_provider():
    """Create a launch template for capacity provider tests."""
    ec2_client = boto3.client("ec2")

    suffix = random_suffix_name("", 8).lstrip("-")
    lt_name = f"ack-ecs-cp-lt-{suffix}"

    lt_resp = ec2_client.create_launch_template(
        LaunchTemplateName=lt_name,
        LaunchTemplateData={
            "ImageId": "resolve:ssm:/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id",
            "InstanceType": "t3.micro",
        },
    )
    lt_id = lt_resp["LaunchTemplate"]["LaunchTemplateId"]

    yield lt_id

    try:
        ec2_client.delete_launch_template(LaunchTemplateName=lt_name)
    except Exception:
        pass


@pytest.fixture(scope="module")
def asg_for_capacity_provider(launch_template_for_capacity_provider):
    """Create an ASG for capacity provider tests."""
    asg_client = boto3.client("autoscaling")
    ec2_client = boto3.client("ec2")
    lt_id = launch_template_for_capacity_provider

    suffix = random_suffix_name("", 8).lstrip("-")
    asg_name = f"ack-ecs-cp-{suffix}"

    vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    vpc_id = vpcs["Vpcs"][0]["VpcId"]
    subnets = ec2_client.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    subnet_ids = [s["SubnetId"] for s in subnets["Subnets"][:2]]

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

    yield asg_arn

    try:
        asg_client.delete_auto_scaling_group(
            AutoScalingGroupName=asg_name, ForceDelete=True
        )
    except Exception:
        pass


@pytest.fixture(scope="module")
def simple_capacity_provider(ecs_client, asg_for_capacity_provider):
    asg_arn = asg_for_capacity_provider
    resource_name = random_suffix_name("ack-ecs-cp", 24)

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

    _, deleted = k8s.delete_custom_resource(
        ref,
        period_length=DELETE_WAIT_AFTER_SECONDS,
    )
    assert deleted

    time.sleep(DELETE_WAIT_AFTER_SECONDS)

    validator = ECSValidator(ecs_client)
    cp = validator.get_capacity_provider(resource_name)
    assert cp is None or cp.get("status") == "INACTIVE"


@service_marker
@pytest.mark.canary
class TestCapacityProvider:
    def test_create(self, ecs_client, simple_capacity_provider):
        (ref, cr, cp_name) = simple_capacity_provider

        k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=10)

        terminal_condition = k8s.get_resource_condition(ref, "ACK.Terminal")
        assert terminal_condition is None or terminal_condition.get("status") != "True", \
            f"Terminal condition set: {terminal_condition}"

        validator = ECSValidator(ecs_client)
        assert validator.capacity_provider_exists(cp_name), \
            f"CapacityProvider {cp_name} not found in AWS"

        cp = validator.get_capacity_provider(cp_name)
        assert cp["name"] == cp_name
        assert cp["status"] == "ACTIVE"
        assert cp["autoScalingGroupProvider"]["managedScaling"]["status"] == "ENABLED"
        assert cp["autoScalingGroupProvider"]["managedScaling"]["targetCapacity"] == 80

        cr = k8s.get_resource(ref)
        assert cr["status"].get("status") == "ACTIVE"

    def test_update_managed_scaling(self, ecs_client, simple_capacity_provider):
        (ref, _, cp_name) = simple_capacity_provider

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

        k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=10)

        validator = ECSValidator(ecs_client)
        cp = validator.get_capacity_provider(cp_name)
        assert cp["autoScalingGroupProvider"]["managedScaling"]["targetCapacity"] == 90
        assert cp["autoScalingGroupProvider"]["managedScaling"]["maximumScalingStepSize"] == 10


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

    time.sleep(60)
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
class TestManagedInstancesCapacityProvider:
    def test_create_managed_instances(self, ecs_client, managed_instances_capacity_provider):
        (ref, _, cp_name, cluster_name) = managed_instances_capacity_provider

        k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=10)

        validator = ECSValidator(ecs_client)
        cp = validator.get_capacity_provider(cp_name)
        assert cp is not None
        assert cp["name"] == cp_name
        assert cp["status"] == "ACTIVE"
        assert cp.get("cluster") is not None

        mip = cp.get("managedInstancesProvider")
        assert mip is not None
        assert mip.get("infrastructureRoleArn") is not None
        assert mip["infrastructureOptimization"]["scaleInAfter"] == 15

    def test_update_managed_instances(self, ecs_client, managed_instances_capacity_provider):
        (ref, _, cp_name, _) = managed_instances_capacity_provider

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

        k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=10)

        validator = ECSValidator(ecs_client)
        cp = validator.get_capacity_provider(cp_name)
        assert cp["managedInstancesProvider"]["infrastructureOptimization"]["scaleInAfter"] == 30
