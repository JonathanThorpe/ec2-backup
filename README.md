# ec2-backup

This Lambda function performs backups of EC2 instances with custom retention schemes based on tags defined against those instances and sends email notifications through SES with a daily status report.

## Installation ##
### IAM Policy Document
The Lambda function requires the following permissions:
* ec2:DescribeInstances
* ec2:DescribeVolumes
* ec2:CreateSnapshot
* ec2:DeleteSnapshot
* ec2:DescribeSnapshots
* ec2:CreateTags
* ses:SendEmail
* ses:SendRawEmail

These can be defined in IAM with the following policy document.
~~~~
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:*"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": "ec2:Describe*",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:CreateSnapshot",
                "ec2:DeleteSnapshot",
                "ec2:CreateTags",
                "ec2:ModifySnapshotAttribute",
                "ec2:ResetSnapshotAttribute"
            ],
            "Resource": [
                "*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendEmail",
                "ses:SendRawEmail"
            ],
            "Resource": "*"
        }
    ]
}
~~~~

### Configuration ###
At the top of the script, a there are a number of configuration directives:
* regions (default: [region where Lambda function is running]) - list of regions to snapshot
* retention_days (default: 2) - integer number of days to keep snapshots. This is overridden by specifying a 'ec2_backup_count' tag on the VM with an integer of the number of backups to retain.
* email_to - Specify an email address to send the logs to
* email_from - Specify an email address to send the emails from.

### SES Verified Senders ###
The Lambda function sends emails to notify administrators that the backup has taken place. This requires some initial setup:

1. Go to Services -> SES
2. Click on Email Addresses.
3. Click "Verify new email address".
4. Enter an email address to verify as a sender - e.g. you@yourdomain.com

An email will be sent to that email address - follow the directions to complete the verification. Also note that if the SES for your AWS account is in sandbox mode, you will also have to verify the recipient email adddress.

### Scheduling
To schedule the backup, perform the following when installing the Lambda script:

1. Click on the Triggers tab.
2. Click "Add Trigger".
3. Add a new trigger source and search for "CloudWatch Events - Schedule". Specify the schedule expression in CRON format e.g. cron(0 3 * * ? *) - 3am UTC. Please note that times are in UTC.

## Configuring EC2 Instances for Backup ##
Each instance you wish to backup requires the following two tags:
* **ec2_backup_enabled:** Must be set to true to enable backups to be taken.
* **ec2_backup_count:** Specifies the number of daily backups to retain.
