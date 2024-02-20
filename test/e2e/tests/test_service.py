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

"""Integration tests for the ECS Service API.
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
from .test_cluster import simple_cluster
from .test_task_definition import simple_task_definitions

RESOURCE_PLURAL = "services"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 15
DELETE_WAIT_AFTER_SECONDS = 30

@pytest.fixture(scope="module")
def simple_service(ecs_client, simple_task_definitions, simple_cluster):
    (_, _, cluster_name) = simple_cluster
    (_, _, task_definition_name) = simple_task_definitions

    resource_name = random_suffix_name("ecs-service", 24)

    replacements = REPLACEMENT_VALUES.copy()

    replacements["SERVICE_NAME"] = resource_name
    replacements["CLUSTER_NAME"] = cluster_name
    replacements["TASK_DEFINITION_NAME"] = task_definition_name

    resource_data = load_ecs_resource(
        "service",
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

    yield (ref, cr, cluster_name, resource_name)

    _, deleted = k8s.delete_custom_resource(
        ref,
        period_length=DELETE_WAIT_AFTER_SECONDS,
    )
    assert deleted

    time.sleep(DELETE_WAIT_AFTER_SECONDS)

    validator = ECSValidator(ecs_client)
    assert validator.task_definition_exists(cr["status"]["ackResourceMetadata"]) is False

@service_marker
@pytest.mark.canary
class TestService:
    def test_create_delete(self, ecs_client, simple_service):
        (ref, _, cluster_name, service_name) = simple_service
        assert service_name is not None

        validator = ECSValidator(ecs_client)
        assert validator.service_exists(cluster_name, service_name)

        # Update settings
        updates = {
            "spec": {
                "desiredCount": 1,
            },
        }
        k8s.patch_custom_resource(ref, updates)
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)

        cs = validator.get_service(cluster_name, service_name)
        assert cs is not None
        assert cs["services"][0]["desiredCount"] == 1