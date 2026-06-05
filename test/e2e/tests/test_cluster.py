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

"""Integration tests for the ECS Cluster API.
"""

import pytest
import time
import logging

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s

from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_ecs_resource
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e.bootstrap_resources import get_bootstrap_resources
from e2e.tests.helper import ECSValidator
from .test_capacity_provider import simple_capacity_provider, asg_for_capacity_provider, launch_template_for_capacity_provider

RESOURCE_PLURAL = "clusters"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10

@pytest.fixture(scope="module")
def simple_cluster(ecs_client):

    resource_name = random_suffix_name("ecs-cluster", 24)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["CLUSTER_NAME"] = resource_name

    resource_data = load_ecs_resource(
        "cluster",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    # Create k8s resource
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
    assert validator.get_cluster(resource_name)["clusters"][0]["status"] == "INACTIVE"

@service_marker
@pytest.mark.canary
class TestCluster:
    def test_create_delete(self, ecs_client, simple_cluster):
        (ref, _, cluster_name) = simple_cluster
        assert cluster_name is not None

        validator = ECSValidator(ecs_client)
        assert validator.cluster_exists(cluster_name)

        # Update settings
        updates = {
            "spec": {
                "settings": [
                    {
                        "name": "containerInsights",
                        "value": "enabled"
                    }
                ],
            },
        }
        k8s.patch_custom_resource(ref, updates)
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)

        cs = validator.get_cluster(cluster_name)
        assert cs["clusters"][0]["settings"][0]["name"] == "containerInsights"
        assert cs["clusters"][0]["settings"][0]["value"] == "enabled"


CP_CREATE_WAIT_AFTER_SECONDS = 60
CP_UPDATE_WAIT_AFTER_SECONDS = 60
CP_DELETE_WAIT_AFTER_SECONDS = 60


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
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)

    time.sleep(CP_CREATE_WAIT_AFTER_SECONDS)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr, resource_name, cp_name)

    _, deleted = k8s.delete_custom_resource(
        ref,
        period_length=CP_DELETE_WAIT_AFTER_SECONDS,
    )
    assert deleted


@service_marker
class TestClusterWithCapacityProviders:
    def test_cluster_default_capacity_provider_strategy(
        self, ecs_client, cluster_with_capacity_providers
    ):
        (ref, _, cluster_name, cp_name) = cluster_with_capacity_providers

        k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=10)

        validator = ECSValidator(ecs_client)
        resp = validator.get_cluster(cluster_name)
        assert resp is not None

        cluster = resp["clusters"][0]
        assert cluster["status"] == "ACTIVE"

        assert cp_name in cluster.get("capacityProviders", [])

        strategy = cluster.get("defaultCapacityProviderStrategy", [])
        assert len(strategy) >= 1
        assert strategy[0]["capacityProvider"] == cp_name
        assert strategy[0]["weight"] == 1
        assert strategy[0]["base"] == 0

    def test_update_cluster_capacity_provider_strategy(
        self, ecs_client, cluster_with_capacity_providers
    ):
        (ref, _, cluster_name, cp_name) = cluster_with_capacity_providers

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
        time.sleep(CP_UPDATE_WAIT_AFTER_SECONDS)

        k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=10)

        validator = ECSValidator(ecs_client)
        resp = validator.get_cluster(cluster_name)
        cluster = resp["clusters"][0]

        strategy = cluster.get("defaultCapacityProviderStrategy", [])
        assert len(strategy) >= 1
        assert strategy[0]["capacityProvider"] == cp_name
        assert strategy[0]["weight"] == 2
        assert strategy[0]["base"] == 1