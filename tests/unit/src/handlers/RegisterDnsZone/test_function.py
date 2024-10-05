import json
import os
import boto3
import moto.route53
import moto.route53.utils
import pytest

from aws_lambda_powertools.utilities.data_classes import (
    CloudFormationCustomResourceEvent,
)
from collections import namedtuple
from moto import mock_aws
from mypy_boto3_route53 import Route53Client
from types import ModuleType
from typing import cast, Dict, Generator, Tuple

from src.handlers.RegisterDnsZone.function import EventResourceProperties

FN_NAME = 'RegisterDnsZone'
DATA_DIR = './data'
FUNC_DATA_DIR = os.path.join(DATA_DIR, 'src/handlers', FN_NAME)
EVENT = os.path.join(FUNC_DATA_DIR, 'event.json')
EVENT_SCHEMA = os.path.join(FUNC_DATA_DIR, 'event.schema.json')
DATA = os.path.join(FUNC_DATA_DIR, 'data.json')
DATA_SCHEMA = os.path.join(FUNC_DATA_DIR, 'data.schema.json')
OUTPUT = os.path.join(FUNC_DATA_DIR, 'output.json')
OUTPUT_SCHEMA = os.path.join(FUNC_DATA_DIR, 'output.schema.json')

#Fixtures
## AWS
@pytest.fixture()
def aws_credentials() -> None:
    '''Mocked AWS Credentials for moto.'''
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def mock_route53_client(aws_credentials) -> Generator[Route53Client, None, None]:
    with mock_aws():
        yield boto3.client('route53')

@pytest.fixture()
def mock_hosted_zone_id(mock_route53_client: Route53Client) -> str:
    '''Return the hosted zone'''
    r = mock_route53_client.create_hosted_zone(
        Name='example.com',
        CallerReference='test',
    )

    return r['HostedZone']['Id']


## Function
@pytest.fixture()
def mock_context() -> Tuple[str, str]:
    '''context object'''
    context_info = {
        'aws_request_id': '00000000-0000-0000-0000-000000000000',
        'function_name': FN_NAME,
        'invoked_function_arn': 'arn:aws:lambda:us-east-1:012345678910:function:{}'.format(FN_NAME),
        'memory_limit_in_mb': 128
    }

    Context = namedtuple('LambdaContext', context_info.keys())
    return Context(*context_info.values())


@pytest.fixture()
def mock_event(event: str = EVENT) -> CloudFormationCustomResourceEvent:
    '''Return a test event'''
    with open(event) as f:
        return CloudFormationCustomResourceEvent(json.load(f))

@pytest.fixture()
def mock_event_create(mock_event: CloudFormationCustomResourceEvent) -> CloudFormationCustomResourceEvent:
    '''Return a test event'''
    mock_event._data['RequestType']
    return mock_event

@pytest.fixture()
def mock_event_update(mock_event: CloudFormationCustomResourceEvent) -> CloudFormationCustomResourceEvent:
    '''Return a test event'''
    mock_event._data['RequestType'] = 'Update'
    return mock_event

@pytest.fixture()
def mock_event_delete(mock_event: CloudFormationCustomResourceEvent) -> CloudFormationCustomResourceEvent:
    '''Return a test event'''
    mock_event._data['RequestType'] = 'Delete'
    return mock_event

@pytest.fixture()
def mock_data(data: str = DATA) -> EventResourceProperties:
    '''Return test data'''
    with open(data) as f:
        # This is an actual data class unlike the type from aws_lambda_powertools
        return EventResourceProperties(**json.load(f))


@pytest.fixture()
def mock_fn(
    mock_route53_client: Route53Client,
    mock_hosted_zone_id: str,
    mocker
) -> Generator[ModuleType, None, None]:
    '''Return the module to be tested'''
    import src.handlers.RegisterDnsZone.function as fn

    # Module patching
    mocker.patch('src.handlers.RegisterDnsZone.function.boto3.client', return_value=mock_route53_client)
    mocker.patch('src.handlers.RegisterDnsZone.function.HOSTED_ZONE_ID', mock_hosted_zone_id)

    yield fn


# Tests
def test_create_or_update_as_create(
    mock_fn: ModuleType,
    mock_context: Tuple[str, str],
    mock_route53_client: Route53Client,
    mock_event_create: CloudFormationCustomResourceEvent,
    mock_data: EventResourceProperties,
    mock_hosted_zone_id: str
) -> None:
    event = mock_event_create._data
    event['ResourceProperties']['ZoneName'] = mock_data.ZoneName
    event['ResourceProperties']['NameServers'] = mock_data.NameServers

    # Call the create_or_update function
    mock_fn.create_or_update(event, mock_context)

    # Verify the NS record was created
    response = mock_route53_client.list_resource_record_sets(
        HostedZoneId=mock_hosted_zone_id
    )

    # check response
    records = response.get('ResourceRecordSets')
    assert records is not None

    # check records
    record = [ rr for rr in records if rr['Name'].rstrip('.') == mock_data.ZoneName ]
    assert len(record) == 1
    assert record[0]['Name'].rstrip('.') == mock_data.ZoneName
    assert record[0]['Type'] == 'NS'

    nameservers = cast(str, mock_data.NameServers).split(',')
    values = [ rr.get('Value') for rr in record[0]['ResourceRecords'] ]
    assert nameservers[0] in values
    assert nameservers[1] in values
    assert nameservers[2] in values
    assert nameservers[3] in values

def test_create_or_update_as_update(
    mock_fn: ModuleType,
    mock_context: Tuple[str, str],
    mock_route53_client: Route53Client,
    mock_event_update: CloudFormationCustomResourceEvent,
    mock_data: EventResourceProperties,
    mock_hosted_zone_id: str
) -> None:
    event = mock_event_update._data
    event['ResourceProperties']['ZoneName'] = mock_data.ZoneName
    event['ResourceProperties']['NameServers'] = mock_data.NameServers

    # Call the create_or_update function
    mock_fn.create_or_update(event, mock_context)

    # Verify the NS record was created
    response = mock_route53_client.list_resource_record_sets(
        HostedZoneId=mock_hosted_zone_id
    )

    # check response
    records = response.get('ResourceRecordSets')
    assert records is not None

    # check records
    record = [ rr for rr in records if rr['Name'].rstrip('.') == mock_data.ZoneName ]
    assert len(record) == 1
    assert record[0]['Name'].rstrip('.') == mock_data.ZoneName
    assert record[0]['Type'] == 'NS'

    nameservers = cast(str, mock_data.NameServers).split(',')
    values = [ rr.get('Value') for rr in record[0]['ResourceRecords'] ]
    assert nameservers[0] in values
    assert nameservers[1] in values
    assert nameservers[2] in values
    assert nameservers[3] in values

def test_delete(
    mock_fn: ModuleType,
    mock_context: Tuple[str, str],
    mock_route53_client: Route53Client,
    mock_event_create: CloudFormationCustomResourceEvent,
    mock_event_delete: CloudFormationCustomResourceEvent,
    mock_data: EventResourceProperties,
    mock_hosted_zone_id: str
) -> None:

    # Create record to be deleted
    create_event = mock_event_create._data
    create_event['ResourceProperties']['ZoneName'] = mock_data.ZoneName
    create_event['ResourceProperties']['NameServers'] = mock_data.NameServers

    # Call the create_or_update function
    mock_fn.create_or_update(create_event, mock_context)

    # Verify the NS record was created
    response = mock_route53_client.list_resource_record_sets(
        HostedZoneId=mock_hosted_zone_id
    )

    # Create delete event
    delete_event = mock_event_delete._data
    delete_event['ResourceProperties']['ZoneName'] = mock_data.ZoneName
    delete_event['ResourceProperties']['NameServers'] = mock_data.NameServers

    # Call the delete function
    mock_fn.delete(delete_event, mock_context)

    # Query zone records for verification
    response = mock_route53_client.list_resource_record_sets(
        HostedZoneId=mock_hosted_zone_id
    )

    records = response['ResourceRecordSets']
    for _rr in records:
        assert _rr['Name'].rstrip('.') != mock_data.ZoneName