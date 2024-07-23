import boto3
from datetime import datetime, timedelta
from dateutil import tz
import time

# Set up AWS Athena client
athena_client = boto3.client('athena', region_name='us-east-1')
sts_client = boto3.client('sts')

account_id = sts_client.get_caller_identity()['Account']
# Define database and table names
data_catalog  = 'AwsDataCatalog'
database_name = 'default'
table_name = 'cloudtrail_logs'
regions = ['ap-east-1','ap-northeast-1','ap-northeast-2','ap-northeast-3','ap-south-1','ap-southeast-1','ap-southeast-2','ca-central-1','eu-central-1','eu-north-1','eu-west-1','eu-west-2','eu-west-3','sa-east-1','us-east-1','us-east-2','us-west-1','us-west-2']
# Define the S3 location for the CloudTrail logs
s3_bucket = 'cloudtrail-awslogs-032998046382-n2o2mj0k-isengard-do-not-delete'
s3_prefix = 'AWSLogs/{}/CloudTrail'.format(account_id)
output_s3 = 's3://freewine-us-east-1/AthenaResults/'

print(s3_prefix)

query_template = '''
ALTER TABLE {table_name} ADD IF NOT EXISTS
   PARTITION (region='{region}',
              year='{year}',
              month='{month}',
              day='{day}')
   LOCATION 's3://{s3_bucket}/{s3_prefix}/{region}/{year}/{month}/{day}/'
'''

# Function to add partitions for a date range
def add_partitions(start_date, end_date):
    for region in regions:
        current_date = start_date
        while current_date <= end_date:
            query = query_template.format(
                table_name=table_name,
                region=region,
                year=current_date.year,
                month='{:02d}'.format(current_date.month),
                day = '{:02d}'.format(current_date.day),
                s3_bucket=s3_bucket,
                s3_prefix=s3_prefix
            )

            # print(query)

            try:
                # Start the query execution
                response = athena_client.start_query_execution(
                    QueryString=query,
                    QueryExecutionContext={'Database': database_name, 'Catalog': 'data_catalog'},
                    ResultConfiguration={
                        'OutputLocation': output_s3
                    }
                )
            except Exception as e:
                print(f"Except: {e}")
            
            time.sleep(0.2)
            current_date = current_date + timedelta(days=1)

# Example usage: Add partitions from 2021-01-01 to today(2024-07-03)
end_date = datetime.now().replace(tzinfo=tz.tzutc())
start_date = datetime.strptime('2021-11-01 00:00:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.tzutc())
add_partitions(start_date, end_date)
