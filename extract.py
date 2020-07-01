#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 29 14:14:32 2020

@author: snehgajiwala
"""

import requests
import pandas as pd
import json  
from pandas.io.json import json_normalize  
import psycopg2
import time
import schedule
from datetime import datetime

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', -1)


def writeData():  
    
    hostname = '127.0.0.1'
    username = 'snehgajiwala'
    password = 'gajiwala'
    database = 'snehgajiwala'
    
    timestr = time.strftime("%Y%m%d-%H%M%S")

    link = 'https://api.omnivore.io/1.0/locations/'
    
    headers = {
        'Api-Key': '3a01cc5779ef4e3784658607fc188719',
    }
    
    response = requests.get(link, headers=headers)
    s = response.text
    j = json.loads(s)
    
    
    df = json_normalize(j['_embedded']['locations'])
    location_ids = df['id'].tolist()
    
    
    link_new = link+location_ids[0]+"/tickets/"
    
    headers = {
        'Api-Key': '3a01cc5779ef4e3784658607fc188719',
    }
    
    response = requests.get(link_new, headers=headers)
    s = response.text
    j = json.loads(s)
    
    fname = "data_"+timestr+".json"
    with open(fname, 'w') as f:
        json.dump(j, f)
    
    df = json_normalize(j['_embedded']['tickets']) 
    
    
    item_name = []
    item_category = []
    for x in df['_embedded.items']:
        x = json_normalize(x)
        if x.empty:
            item_name.append("None")
            item_category.append("None")
        else:
            item_all = x['_embedded.menu_item.name']
            cat_j = x['_embedded.menu_item._embedded.menu_categories']
            items = ', '.join(item_all.tolist())
            cat_all = []
            for q in cat_j:
                p = json_normalize(q)
                c = p['name']
                c = set(c)
                l = ', '.join(list(c))
                cat_all.append(l)
                cat_all = list(set(cat_all))
            categories = ', '.join((cat_all))
    
            item_name.append(items)
            item_category.append(categories)
            
    
    new_df = pd.DataFrame()
    new_df['Ticket_ID'] = df['id']
    new_df['Total'] = df['totals.total']/100
    new_df['Subtotal'] = df['totals.sub_total']/100
    new_df['Tax'] = df['totals.tax']/100
    new_df['Tips'] = df['totals.tips']/100
    new_df['Opened At'] = df['opened_at']
    new_df['Closed At'] = df['closed_at']
    new_df['Order Type'] = df['_embedded.order_type.name']
    new_df['Item Name'] = item_name
    new_df['Category Name'] = item_category
    new_df['Closed At'] = new_df['Closed At'].fillna("None")
    
    opened_unix = df['opened_at'].tolist()
    closed_unix = df['closed_at'].tolist()
    opened_ts = []
    closed_ts = []
    for i in opened_unix:
        ts = int(i)
        opened_ts.append(datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'))
    for j in closed_unix:
        ts = int(i)
        closed_ts.append(datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'))    
    new_df['Opened At'] = opened_ts
    new_df['Closed At'] = closed_ts

    
    fname = 'ProductionData_'+timestr +'.csv'
    new_df.set_index("Ticket_ID", inplace = True) 
    new_df.to_csv("fname")
   
    
    connection = psycopg2.connect( host=hostname, user=username, password=password, dbname=database )
    cursor = connection.cursor()
    
    
    
    cursor.execute( "SELECT ticketid FROM OmnivoreDatanew" )
    existing_tickets = []
    for tId in cursor.fetchall() :
        existing_tickets.append(str(tId[0]))
        
    new_df=new_df[~new_df['Ticket_ID'].isin(existing_tickets)]
    
    
    if not new_df.empty:
        for Ticket_ID, record in new_df.groupby('Ticket_ID'):
            ticketId = str(record['Ticket_ID'].values[0])
            total = str(record['Total'].values[0])
            subtotal = str(record['Subtotal'].values[0])
            tax = str(record['Tax'].values[0])
            tips = str(record['Tips'].values[0])
            openedAt = str(record['Opened At'].values[0])
            closedAt = str(record['Closed At'].values[0])
            orderType = str(record['Order Type'].values[0])
            itemName = str(record['Item Name'].values[0])
            catName = str(record['Category Name'].values[0])
    
    
    
            postgres_insert_query =  "INSERT INTO OmnivoreDatanew VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);"
            record_to_insert = (ticketId,total,subtotal,tax,openedAt,closedAt,orderType,itemName,catName,tips)
            cursor.execute(postgres_insert_query, record_to_insert)
            connection.commit()
        
        print("Records inserted")
    
    else:
        print("Database is up to date")
    
    master_df = pd.DataFrame(columns=['Ticket ID','Total','Subtotal','Tax','Opened At','Closed At','Order Type','Item Name','Category Name','Tips'])

    cursor.execute( "SELECT * FROM OmnivoreDatanew" )
    existing_tickets = []
    for (ticketId,total,subtotal,tax,openedAt,closedAt,orderType,itemName,catName,tips) in cursor.fetchall() :
        master_df.loc[len(master_df)]=[ticketId,total,subtotal,tax,openedAt,closedAt,orderType,itemName,catName,tips]
    
    master_df.set_index("Ticket ID", inplace = True) 
    master_df.to_csv("MasterDataset.csv")
    
    cursor.close()
    connection.close()

schedule.every().day.at("09:00").do(writeData)


while True:
    schedule.run_pending()
    time.sleep(1)