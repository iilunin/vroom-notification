from __future__ import print_function
import os
import json
import requests
from datetime import datetime


import boto3


def main(event, context):
    price = os.environ.get('price', 16000)
    miles = os.environ.get('miles', 20000)
    dir = '{p}_{m}'.format(p=price, m=miles)
    data_file = os.path.join(dir, 'data.json')

    s3 = boto3.resource('s3')
    bucket = s3.Bucket(os.environ.get('bucket'))

    data = None

    url = 'https://invsearch.vroomapi.com/v2/inventory?brand=vroom&sort=&offset=0&limit=100&' \
          'price_max={p}&miles_max={m}&year_max=all-years&year_min=all-years&mm=all-makes'.format(p=price, m=miles)

    r = requests.get(url)

    if r.status_code == 200:
        data = r.json()

    if not data:
        return

    bucket_key = list(bucket.objects.filter(Prefix=dir))

    checked_vins = None

    if len(bucket_key) > 0:
        data_files = list(bucket.objects.filter(Prefix=data_file))
        if len(data_files) > 0:
            existing_vins_obj = bucket.Object(data_file)
            contents = existing_vins_obj.get()['Body'].read().decode('utf-8')
            old_vins = json.loads(contents)
            checked_vins = [v['attributes']['vin'] for v in old_vins]

    else:
        bucket.put_object(Key=dir+'/')

    new_cars_file = os.path.join(dir, datetime.now().__format__('%Y%m%d_%H%M%S') + '.txt')

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

        if checked_vins and car.get('vin') in checked_vins:
            continue

        carline = '{make} {model} {year}. ${listingPrice}, {miles} mi. Warranty remaining:{warrantyRemaining}, ' \
                  'VIN: {vin}, url:https://www.vroom.com/inventory/{vin} carfax:{uriCarfax}'.format(**car)
        print(carline)
        new_cars += carline+os.linesep
        num_new_cars += 1

    if new_cars:
        bucket.put_object(Key=new_cars_file, Body=new_cars)
        bucket.put_object(Key=data_file, Body=json.dumps(data.get('data')))

        if os.environ.get('topic_arn'):
            sns = boto3.client('sns')

            sns.publish(TopicArn=os.environ.get('topic_arn'),
                        Subject='New Vroom Stuff',
                        Message=new_cars)

            cellphone = os.environ.get('cellphone')

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
