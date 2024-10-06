import os
import boto3
from crhelper import CfnResource
from dataclasses import dataclass
from mypy_boto3_route53 import Route53Client
from mypy_boto3_route53.type_defs import ChangeBatchTypeDef, ChangeResourceRecordSetsRequestRequestTypeDef
from typing import Optional

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    CloudFormationCustomResourceEvent,
    event_source
)
helper = CfnResource()

try:
    ROUTE53: Route53Client = boto3.client('route53')
    # FIXME: We should be able to set the service name from the environment.
    LOGGER = Logger(utc=True, service="RegisterDnsZone")
    HOSTED_ZONE_ID = os.environ.get('HOSTED_ZONE_ID', '')

    if HOSTED_ZONE_ID == '':
        raise ValueError("HOSTED_ZONE_ID must be provided")

except Exception as e:
    helper.init_failure(e)


@helper.create
@helper.update
@event_source(data_class=CloudFormationCustomResourceEvent)
def create_or_update(event: CloudFormationCustomResourceEvent, _: LambdaContext):
    # Extract ResourceProperties from the event
    zone_name = event.resource_properties.get('ZoneName')
    nameservers = event.resource_properties.get('NameServers')

    if not zone_name:
        raise ValueError("ZoneName must be provided")
    if not nameservers:
        raise ValueError("NameServers must be provided")
    else:
        nameservers = nameservers.split(',')

    if not zone_name.endswith('.'):
        zone_name += '.'

    LOGGER.info(
        "Creating zone NS record",
        extra = {
            'zone_name': zone_name,
            'nameservers': nameservers
        }
    )

    # Create the change batch for the NS record
    change_batch: ChangeBatchTypeDef = {
        'Comment': 'Upsert NS record for the zone {}'.format(zone_name),
        'Changes': [
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': zone_name,
                    'Type': 'NS',
                    'TTL': 300,
                    'ResourceRecords': [{'Value': ns.strip()} for ns in nameservers]
                }
            }
        ]
    }

    change_args: ChangeResourceRecordSetsRequestRequestTypeDef = {
        'HostedZoneId': HOSTED_ZONE_ID,
        'ChangeBatch': change_batch
    }

    # Update the Route 53 hosted zone with the new NS record
    response = ROUTE53.change_resource_record_sets(**change_args)

    LOGGER.info("Change Info: {}".format(response['ChangeInfo']))

    return response['ChangeInfo']['Id']


@helper.delete
@event_source(data_class=CloudFormationCustomResourceEvent)
def delete(event: CloudFormationCustomResourceEvent, context: LambdaContext):
    # Extract ResourceProperties from the event
    zone_name = event.resource_properties.get('ZoneName')
    nameservers = event.resource_properties.get('NameServers')

    if not zone_name:
        raise ValueError("ZoneName must be provided")

    if not nameservers:
        raise ValueError("NameServers must be provided")
    else:
        nameservers = nameservers.split(',')

    LOGGER.info(
        "Deleting zone NS record",
        extra = {
            'zone_name': zone_name,
            'nameservers': nameservers
        }
    )

    # Create the change batch to delete the NS record
    change_batch: ChangeBatchTypeDef = {
        'Changes': [
            {
                'Action': 'DELETE',
                'ResourceRecordSet': {
                    'Name': zone_name,
                    'Type': 'NS',
                    'TTL': 300,
                    'ResourceRecords': [{'Value': ns.strip()} for ns in nameservers]
                }
            }
        ]
    }

    # Delete the NS record from the Route 53 hosted zone
    response = ROUTE53.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch=change_batch
    )

    LOGGER.info("Change Info: {}".format(response['ChangeInfo']))
