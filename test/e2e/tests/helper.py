# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Helper functions for ECS e2e tests
"""

import logging

class ECSValidator:
    def __init__(self, ecs_client):
        self.ecs_client = ecs_client

    def get_cluster(self, cluster_name: str) -> dict:
        try:
            resp = self.ecs_client.describe_clusters(
                clusters=[cluster_name],
                include=["SETTINGS"],
            )
            return resp

        except Exception as e:
            return None

    def cluster_exists(self, cluster_name) -> bool:
        return self.get_cluster(cluster_name) is not None

    def get_task_definition(self, task_definition_arn: str) -> dict:
        try:
            resp = self.ecs_client.describe_task_definition(
                taskDefinition=task_definition_arn,
            )
            return resp

        except Exception as e:
            return None
    
    def task_definition_exists(self, task_definition_name) -> bool:
        return self.get_task_definition(task_definition_name) is not None
