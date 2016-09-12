# AWS Lambda Python script to snapshot all EC2 volumes and delete snapshots older than retention time
#
# Originally inspired by https://github.com/viyh/aws-scripts/blob/master/lambda_autosnap.py
# 
# Required IAM permissions:
#   ec2:DescribeInstances
#   ec2:DescribeVolumes
#   ec2:CreateSnapshot
#   ec2:DeleteSnapshot
#   ec2:DescribeSnapshots
#   ec2:CreateTags
#   ses:SendEmail
#   ses:SendRawEmail
#
# config parameters (either passed through the config variable, or if it's set to None, then through the event interface:
#   * regions (default: [region where Lambda function is running])
#       list of regions to snapshot
#   * retention_days (default: 2)
#       integer number of days to keep snapshots. This is overridden by specifying a 'ec2_backup_count' tag on the VM with an integer of the number of backups to retain.
#   * email_to:
#       Specify an email address to send the logs to
#   * email_from:
#        Specify an email address to send the emails from.
#
#  Enabling backups: - Instances require a coule of tags:
#   * ec2_backup_enabled:
#        Enables the backup
#   * ec2_backup_count:
#        Specifies a retention period in days
#

import boto3
import json, datetime
from datetime import tzinfo, timedelta, datetime

#Set config to None if you would like to pass this information through event data.
config = {
  "regions": ["us-west-1"],
  "retention_days": "7",
  "email_from": "user@localhost.localdomain",
  "email_to": "you@localhost.localdomain"
}

logBuffer = []

def logMessage(message):
    global logBuffer
    logBuffer.append({ 'timestamp': datetime.now(),
                       'message': message })
    
    print("%s: %s\n" % (logBuffer[-1]['timestamp'], logBuffer[-1]['message']))

def getTagValue(key, tags):
    pair = [t for t in tags if t['Key'] == key]
    if (len(pair) > 0):
        return pair[0]['Value']

    return None

def emailLogBuffer(email_from, email_to, logbuf):
    email_subject = "EC2 Snapshot Backup Report - %s" % (datetime.now().strftime("%Y-%m-%d"))
    client = boto3.client('ses')
    client.send_email(
        Source = email_from,
        Destination = {
            'ToAddresses': [email_to]
        },
        Message = {
            'Subject': {
                'Data': email_subject,
                'Charset': 'UTF-8'
            },
            'Body': {
                'Text': {
                    'Data': '\n'.join("%s: %s" % (log['timestamp'], log['message']) for log in logbuf),
                    'Charset': 'UTF-8'
                }
            }
        }
    )

def lambda_handler(event, context):
    global logBuffer, config

    if (config is None):
        config = event

    regions = [context.invoked_function_arn.split(':')[3]]
    if 'regions' in config:
        regions = config['regions']

    retention_days = 2
    if 'retention_days' in config:
        retention_days = config['retention_days']

    logMessage("AWS snapshot backups starting")
    for region in regions:
        logMessage("Region: %s" % region)
        create_region_snapshots(region, retention_days)

    email_from = None
    if 'email_from' in config:
        email_from = config['email_from']

    email_to = None
    if 'email_to' in config:
        email_to = config['email_to']

    logMessage("AWS snapshot backups completed")

    if (email_from is not None and email_to is not None):
        emailLogBuffer(email_from, email_to, logBuffer)

# create snapshot for region
def create_region_snapshots(region, retention_days):
    ec2 = boto3.resource('ec2', region_name=region)
    instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']},
                                              {'Name': 'tag:ec2_backup_enabled', 'Values': ['true', 'True']}])
    for i in instances:
        instance_name = filter(lambda tag: tag['Key'] == 'Name', i.tags)[0]['Value']
        volumes = ec2.volumes.filter(Filters=[{'Name': 'attachment.instance-id', 'Values': [i.id]}])

        inst_retention = retention_days
        config_count = getTagValue('ec2_backup_count', i.tags)
        if (config_count is not None):
            inst_retention = config_count

        logMessage("Instance name: %s, Instance ID: %s, Retention Period: %s days." % (instance_name, i.id, inst_retention))
        snapshot_volumes(instance_name, int(inst_retention), volumes)
        logMessage("Backup complete for instance %s (%s)" % (instance_name, i.id))

# create and prune snapshots for volume
def snapshot_volumes(instance_name, retention_days, volumes):
    for v in volumes:
        logMessage("Volume found: %s" % v.volume_id)
        create_volume_snapshot(instance_name, v)
        prune_volume_snapshots(retention_days, v)

# create snapshot for volume
def create_volume_snapshot(instance_name, volume):
    description = 'autosnap-%s.%s-%s' % ( instance_name, volume.volume_id,
        datetime.now().strftime("%Y%m%d-%H%M%S") )
    snapshot = volume.create_snapshot(Description=description)
    if snapshot:
        snapshot.create_tags(Tags=[{'Key': 'Name', 'Value': description}])
        logMessage("Snapshot created with description [%s]" % description)

# find and delete snapshots older than retention_days
def prune_volume_snapshots(retention_days, volume):
    for s in volume.snapshots.all():
        now = datetime.now(s.start_time.tzinfo)
        old_snapshot = ( now - s.start_time ) > timedelta(days=retention_days)
        if not old_snapshot or not s.description.startswith('autosnap-'): continue
        logMessage("Deleting snapshot [%s - %s] created [%s]" % ( s.snapshot_id, s.description, str( s.start_time )))
        s.delete()
