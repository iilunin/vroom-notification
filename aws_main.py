from __future__ import print_function  # for AWS logging
import os
import json
import requests
from datetime import datetime


import boto3


def main(event, context):
    price = os.environ.get('CAR_PRICE')
    miles = os.environ.get('CAR_MILEAGE')

    output_dir = '{p}_{m}'.format(p=price, m=miles)
    data_file = os.path.join(output_dir, 'data.json')

    url = 'https://invsearch.vroomapi.com/v2/inventory?brand=vroom&sort=&offset=0&limit=1000&' \
          'price_max={p}&miles_max={m}&year_max=all-years&year_min=all-years&mm=all-makes'.format(p=price, m=miles)

    r = requests.get(url)

    data = None
    if r.status_code == 200:
        data = r.json()
    else:
        print('Issues downloading data from the "{url}", error code: {status}'.format(url=url, status=r.status_code))

    if not data:
        return

    s3 = boto3.resource('s3')
    bucket = s3.Bucket(os.environ.get('S3_BUCKET'))
    bucket_key = list(bucket.objects.filter(Prefix=output_dir))

    previous_vins = None

    # Check if we have stored JSON data file in the bucket before.
    if len(bucket_key) > 0:
        data_files = list(bucket.objects.filter(Prefix=data_file))
        if len(data_files) > 0:
            existing_vins_obj = bucket.Object(data_file)
            contents = existing_vins_obj.get()['Body'].read().decode('utf-8')
            old_vins_data = json.loads(contents)
            previous_vins = {v['attributes']['vin']: v['attributes']['isAvailable'] for v in old_vins_data}

    else:
        bucket.put_object(Key=output_dir+'/')  # Create 'folder' in S3

    new_cars_file = os.path.join(output_dir, datetime.now().__format__('%Y%m%d_%H%M%S') + '.txt')

    new_cars = ''
    num_new_cars = 0
    for car_item in data.get('data'):
        car = car_item.get('attributes')

        if not car.get('isAvailable', True):
            continue

        if car.get('model', '').lower() == 'motorcycle':
            continue

        if car.get('transmission', '') == 'manual':
            continue

        # only skip if the car was in the list and was available.
        # If it was unavailable and then become available consider it as a newly listed
        if previous_vins and car.get('vin') in previous_vins:
            if previous_vins[car.get('vin')]:
                continue

        carline = '{make} {model} {year}. ${listingPrice}, {miles} mi. Warranty remaining:{warrantyRemaining}, ' \
                  'VIN: {vin}, url:https://www.vroom.com/inventory/{vin} carfax:{uriCarfax}'.format(**car)
        print(carline)
        new_cars += carline+os.linesep
        num_new_cars += 1

    if new_cars:
        bucket.put_object(Key=new_cars_file, Body=new_cars)
        bucket.put_object(Key=data_file, Body=json.dumps(data.get('data')))

        sns_topic = os.environ.get('SNS_TOPIC_ARN')

        if sns_topic:
            sns = boto3.client('sns')

            sns.publish(TopicArn=sns_topic,
                        Subject='New Vroom Stuff',
                        Message=new_cars)

            cellphone = os.environ.get('CELLPHONE')

            if cellphone:
                sns.publish(
                    PhoneNumber=cellphone,
                    Subject='New Vroom Stuff',
                    Message='Checkout email for the New Vroom Stuff')

        print('Found {0} new cars'.format(num_new_cars))
        return {'message': new_cars}

    else:
        print('No new cars available')


if __name__ == '__main__':
    main(None, None)
