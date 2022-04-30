'''author :mayuri date:4/16/2022'''


# Imports ObjectId to convert to the correct format before querying in the db
from asyncore import read
import email
from bson.objectid import ObjectId
from random import randint
import random,json
import datetime
import requests
from src.Util.CommonUtil import CommonUtil
from src.Taxi.taxi_services import Taxi_Services

# customer document contains customer_name (String), email (String), and role (String) fields
class Customer_Services():
    customer_data_list = []

    def __init__(self):
        self._latest_error = ''
        config = CommonUtil.read_properties()
        self._customer_file_path = config.get("CUSTOMER_CSV_FILE").data
        self._collection_name = config.get("CUSTOMER_COLLECTION").data
        self._json_file_path = config.get("AREA_BOUNDARY_JSON_PATH").data
        self.post_url = config.get("POST_URL").data   
        self.get_url = config.get("GET_URL").data 
        self.book_url = config.get("BOOK_URL").data 
        self.email_url = config.get("EMAIL_URL").data
        self._location_data_json()
    
    def _location_data_json(self):
        with open(self._json_file_path, "r") as jsonFile:
            json_data = json.load(jsonFile)
        self._min_lat = float(json_data[0]["area_0"]["MIN_LAT_VALUE"])
        self._max_lat = float(json_data[0]["area_0"]["MAX_LAT_VALUE"])
        self._min_long = float(json_data[0]["area_0"]["MIN_LONG_VALUE"])
        self._max_long = float(json_data[0]["area_0"]["MAX_LONG_VALUE"])
    
    # Latest error is used to store the error string in case an issue. It's reset at the beginning of a new function call
    @property
    def latest_error(self):
        return self._latest_error

    # Reads customer.csv one line at a time, splits them into the data fields and inserts
    def read_data_from_csv(self):
        customer_data_list = []
        with open(self._customer_file_path, 'r') as customer_fh:
            for customer_row in customer_fh:
                customer_row = customer_row.rstrip()
                if customer_row:
                    (customer_first_name, customer_last_name,customer_type,customer_email,trip_indicator) = customer_row.split(',')                            
                customer_data = {"customer_first_name": customer_first_name,"customer_last_name": customer_last_name,"customer_email":customer_email,"customer_type":customer_type,"trip_indicator":trip_indicator}
                customer_data_list.append(customer_data)
            return customer_data_list
            
    # generate uniques customer id 
    def generate_customer_id(self,cust_first,cust_last):
        start = randint(1,10)
        end = randint(11,20)
        rand_num = randint(start,end)
        cust_name = cust_first[:4]+cust_last[:2]
        cust_id = f"{cust_name}_{rand_num}"        
        return cust_id

    # •	Service area validation: check for area boundary
    def check_location(self,lat,long):
        if self._min_lat <=  lat <= self._max_lat  and  self._min_long <=  long <= self._max_long:
            return 1
        return -1
        
    # register one customer
    def register_one(self,customer_first_name,customer_last_name,customer_email,customer_type,lat,long):
        try:
            self._latest_error = '' 
            # check location cordinates
            loc_res = self.check_location(lat,long)
            if loc_res != -1:
                # read customer customer details           
                res = self.get_customer_details(customer_first_name,customer_last_name)
                cust_res = json.loads(res)
                if cust_res == -1:                          
                    customer_id = self.generate_customer_id(customer_first_name,customer_last_name)
                    _timestamp=datetime.datetime.now()
                    customer_data = {"timestamp":str(_timestamp),"customer_id":customer_id,"customer_type":customer_type,"customer_first_name": customer_first_name,"customer_last_name": customer_last_name,"customer_email":customer_email,"trip_indicator":"OFF","location":{"type":"Point","coordinates":[long,lat]}}        
                    reg_res = self.register_connection([customer_data]) 
                    if reg_res["res"] != -1:
                        self.send_email(reg_res)  
                        print("==================Successful Registration!==================")            
                else:
                    print("============Customer already registered!! ====================")
            else:
                print("Sorry, Cab service is not provided at this location!")
        except Exception as e:
            print("RegisterOneError:",str(e))

    # Customer simulation: registers many customer from list/csv files
    def register_many(self):
        try:
            customer_data = self.read_data_from_csv()
            for val in customer_data:
                customer_id = self.generate_customer_id(val['customer_first_name'],val['customer_last_name'])
                _timestamp=datetime.datetime.now()
                long = random.uniform(self._min_long, self._max_long)
                lat = random.uniform(self._min_lat, self._max_lat)
                val["timestamp"] = str(_timestamp)
                val["customer_id"]=customer_id
                val["location"]={"type":"Point","coordinates":[long,lat]}
                self.customer_data_list.append(val)
            self.register_connection(self.customer_data_list)
        except Exception as e:
            print("RegisterManyError:",str(e))        

    # connect to API gateway for registration
    def register_connection(self,cust_data):
        #creaating json data
        customer_data = json.dumps(cust_data)
        # connecting to endpoint to send data
        res = requests.post(self.post_url,data=customer_data)
        reg_res = json.loads(res.text)
        if reg_res["res"] != -1:
            print("==================Connected to Register API==================")
            return reg_res
        else:
            print("Check status!")
            return {"res":-1}

    # connect to API gateway to read customer details
    def get_customer_details(self,customer_first_name,customer_last_name):
        try:
            data_req = {"req":"one","customer_first_name":customer_first_name,"customer_last_name":customer_last_name}
            # connecting to endpoint to send data
            response = requests.get(self.get_url,params = data_req)            
            return response.text
        except:
            return -1
    
    # get data for all customer
    def get_registered_customers(self):
        try:
            data_req = {"req":"all"}
            # connecting to endpoint to send data
            response = requests.get(self.get_url,params = data_req)            
            return response.text
        except:
            return -1

    # Booking and proximity search : raise booking request and return nearest taxi via API
    def booking(self,customer_first_name,customer_last_name,source_lat,source_long,dest_lat,dest_long,taxi_type):
        # check if source/destination location is in service area boundary
        source_res= self.check_location(source_lat,source_long)
        dest_res = self.check_location(dest_lat,dest_long)
        if source_res != -1 and dest_res != -1:
            try:
                # read customer customer details           
                res = self.get_customer_details(customer_first_name,customer_last_name)
            except Exception as e:
                print(str(e))         
            read_res = json.loads(res)
            if read_res != -1:
                # check if customer is "General" and  already in trip
                cust_trip_ind = read_res["trip_indicator"]
                cust_type = read_res["customer_type"]
                if cust_trip_ind == "ON" and cust_type == "General":
                    print("Customer not premium member, not allowed to book taxi while in trip !")
                else:
                    # connecting to endpoint to send data
                    cust_id = read_res["customer_id"]
                    cust_email = read_res["customer_email"]
                    _timestamp=datetime.datetime.now()
                    customer_type = read_res["customer_type"]
                    cust_data = {"timestamp":str(_timestamp),"customer_id": cust_id,"customer_first_name": customer_first_name,"customer_last_name": customer_last_name,"email_id":cust_email,"customer_type":customer_type,"source_lat":source_lat,"source_long":source_long,"type":"Point","taxi_type":taxi_type,"dest_lat":dest_lat,"dest_long":dest_long}
                    response = requests.get(self.book_url,params = cust_data)
                    book_res = json.loads(response.text)
                    customer_name = customer_first_name + " " + customer_last_name
                    # print(book_res)
                    self.send_email(book_res)
                    if book_res["res"] != -1 :
                        print("Connected to Booking API Endpoint")
                        print(f"=========Booking Successful for customer : {customer_name}!!===========")                    
                        book_res.pop("msg")
                        book_res.pop("email_id")
                        book_res.pop("res")
                        self.customer_trip(book_res)
                        # return book_res
                    elif book_res["res"] == -1:
                        print(f"Check status in booking table for customer: {customer_name}")
                        return -1
                    else:
                        print("Faiulre!!")
                        return -1
            else:
                print("Customer not registered for services!")
                return 0
        else:
            print("Sorry,cab service is not available in source/destination area!") 


    def send_email(self,cust_data):
        #creaating json data
        customer_data = json.dumps(cust_data)
        # connecting to endpoint to send email
        res = requests.post(self.email_url,data=customer_data)
        email_res = json.loads(res.text)
        if email_res == 1:
            print("=========email sent to customer!===========")
        elif email_res == 0:
            print("Email needs to be verified by customer!")
        else:
            print("Check status! Mostly email id not valid!")

    # customer trip method 
    def customer_trip(self,booking_details):
        taxi_services = Taxi_Services()
        trip_res = taxi_services.start_trip(booking_details)


