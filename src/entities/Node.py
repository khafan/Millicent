'''
Created on Jan 30, 2015

@author: AlirezaF
'''
from entities.Message import *
from entities.Scrip import *
from random import randrange
from Crypto.Random.random import sample
from entities.Network import *
from time import time
from statics.Utils import get_hmac


#===============================================================================
# Node
#===============================================================================
class Node():
    '''
    Base class for a node in network. A node can be one of the customer, vendor or broker
    '''

    def __init__(self, network, net_id):
        '''
        net_id is the unique id of this node in network
        '''
        self.network = network
        self.id = net_id
        
    #TODO encode thing
    def send_msg(self, message):
        '''
        sends the message into network. receiver
        ''' 
        # self.network.deliver_msg(message)
        pass    

    #TODO decode thing
    def receive_msg(self, message):
        self.process_msg(message)    
    
    def process_msg(self, message):
        '''
        Splits the message into parts specified by ------ line
        '''
        msg = dict(zip(["type", "sender", "receiver", "data"], message.split("---")))
        msg["data"] = msg["data"].split(Message.data_seg)
        return msg 
    
    
    def parse_scrip(self, string):
        # TODO: parse scrip from string representation
        j = json.loads(string)
        return Scrip(j['vendor_id'], j['id'], j['cust_id'], j['expiry'],j['amount'], j['certificate'])


#===============================================================================
# Broker
#===============================================================================

class Broker(Node):
    '''
    Knows vendors in network and has their secret keys
    Customer buy broker Scrip by sending request and receiving Scrip in plain text.
    '''
    broker_expiry = 120 # in seconds
    vendor_expiry = 60 
    
    def __init__(self, network, net_id, vendors):
        Node.__init__(self, network, net_id)
        self.vendors = vendors
        
        self.valid_scripsIDs = sample(range(0, 0xFFFFFFFF), 1000)
        self.used_scripsIDs = []
    
    def process_msg(self, message):
        msg = Node.process_msg(self, message)
        
        if msg["type"] == "RequestBrokerScrip":
            scrip = Scrip("", self.generate_scripID(), msg["sender"],
                           self.get_broker_expiry(), msg["data"][0])
            scrip.set_certificate(get_md5(scrip))
            
            self.send_msg(ResponseBrokerScrip(self.id, msg["sender"], scrip))
            
        elif msg["type"] == "RequestVendorScrip":
            # mojudie broker scrip va mizani ke vendor scrip mikhad 
            # ba tavajjoh be ham barresi shan
            # TODO: incomplete
            
            vendor_id = msg["data"][0]
            vendor_scrip_amount = self.parse_scrip(msg["data"][1])
            broker_scrip = self.parse_scrip(msg["data"][2])
            cust_id = msg["sender"]
            
            vendor_scrip = Scrip(vendor_id, self.generate_scripID(), cust_id, self.get_expiry(), vendor_scrip_amount)
            
            broker_change_scrip = Scrip("", self.generate_scripID(), cust_id, self.get_broker_expiry(), broker_scrip.amount - vendor_scrip_amount)
            
            self.used_scripsIDs.append(broker_scrip.id)
            
            
            self.send_msg(ResponseVendorScrip(self.id, cust_id, vendor_scrip, broker_change_scrip))    
        
    def get_broker_expiry(self):
        return int(time() + self.broker_expiry) # a scrip lasts for only 10 minute
    
    def get_vendor_expiry(self):
        return int(time() + self.vendor_expiry)
    
    def generate_scripID(self):
        '''
        creates a new unique id for scrip.
        '''
        id = self.valid_scripsIDs.pop()
        self.used_scripsIDs.append(id)
        return id 
  
  
  
  
  #=============================================================================
  # CUSTOMER
  #=============================================================================
  
  
class Customer(Node):
    '''
    Has a unique ID in network, buy scrip from broker and uses that in 
    '''                
    def __init__(self, network, net_id, money):
        Node.__init__(self, network, net_id)
        self.money = money
        self.borker_scrips = []
        # for picking a vendor scrip, we must search and find one which has same vendor id as
        # vendor we want to purchase from.
        self.vendor_scrips = []
        self.products = []
        
    def add_broker_scrip(self, scrip):
        self.broker_scrips.append(scrip)
            
    def add_vendor_scrip(self, scrip):
        self.vendor_scrips.append(scrip)    
    
    
    def buy_broker_scrip(self, amount):
        '''
        requests a scrip from broker with the amount given.
        money will be reduced in processing the response.
        '''
        self.send_msg(RequestBrokerScrip(self.id, self.network.broker_id, amount))
        
    
    def buy_vendor_scrip(self, amount, vendor_id):
        broker_scrip = self.find_broker_scrip(amount) # TODO: needs testing
        self.send_msg(RequestVendorScrip(self.id, self.network.id, vendor_id, amount, broker_scrip))
    
    
    def buy_product(self, vendor_id, product_price):
        vendor_scrip = self.find_vendor_scrip(product_price)
        self.send_msg(RequestBuyProduct(self.id, vendor_id, vendor_scrip))
            
        
    def find_broker_scrip(self, amount):
        return self.__find_scrip(amount, self.borker_scrips)
         
    def find_vendor_scrip(self, amount):
        return self.__find_scrip(amount, self.vendor_scrips)
    
    def __find_scrip(self, amount, scrips):
        scrip = next(scrip for scrip in scrips if scrip.amount >= amount)
        scrips.remove(scrip)
        return scrip
     
    def parse_product(self, string):
        # TODO:
        return None            
        

    
    def process_msg(self, message):
        msg = Node.process_msg(self, message)
        broker = msg["sender"]
        
        if msg["type"] == "ResponseBrokerScrip":
            scrip = self.parse_scrip(msg["data"][0])
            self.money -= scrip.amount
            self.add_broker_scrip(scrip)
            
        
        elif msg["type"] == "ResponseVendorScrip":
            vendor_scrip = self.parse_scrip(msg["data"][0])
            self.add_vendor_scrip(vendor_scrip)
            
            broker_change = msg["data"][1]
            if broker_change:
                broker_change_scrip = self.parse_scrip(broker_change)
            self.add_broker_scrip(broker_change_scrip)
            
        
        elif msg["type"] == "ResponseProductInfo":
            return (msg["data"][0], msg["data"][1]) # name and price
         
        
        elif msg["type"] == "ResponseBuyProduct":
            self.products.append(self.parse_product(msg["data"][0])) # TODO: parse product from string
            vendor_change = msg["data"][1]
            if vendor_change:
                self.add_vendor_scrip(self.parse_scrip(vendor_change))
                
        
    
    
    
    
#===============================================================================
# VENDOR  
#===============================================================================
    
class Vendor(Node):
    '''
    '''
    
    def __init__(self, product):
        '''
        product is the class object of product type this vendor will sell
        '''
        self.create_mss() # Master_scrip_secret. 
        self.create_mcs() # Master_customer_secret.
        self.used_scrips = []
        self.product = product
    
    def create_product(self):
        self.products = [self.product() for i in range(100)]
    
    def product_info(self):
        return self.product.name + " " + self.product.price    
        
    def create_mss(self):
        '''
        creates ten random integer as Master Scrip secrets.
        '''
        self.mss = sample(randrange(0, 0xFFFFFFFF), 10) 
        
        
    def create_mcs(self):
        '''
        creates ten random integer as Master customer secrets.
        '''
        self.mss = sample(randrange(0, 0xFFFFFFFF), 10)
        

    def process_msg(self, message):
        msg = Node.process_msg(self, message)
        cust_id = msg["sender"]
        
        if msg["type"] == "RequestProducInfo":
            self.send_msg(ResponseProductInfo(self.id, cust_id, self.product.name, self.product.price))
            
        elif msg["type"] == "RequestBuyProduct":
            vendor_scrip = self.parse_scrip(msg["data"][0])
            
            vendor_change_scrip = Scrip(self.id, cust_id, self.get_expiry(), vendor_scrip.amount - self.product.price)
            self.used_scrips.append(vendor_scrip.id)
            
            self.send_msg(ResponBuyProduct(self.id, cust_id, vendor_change_scrip, self.products.pop()))
    
    
    def get_expiry(self):
        return int(time() + self.vendor_expiry)
    
        
# s = Scrip(123, 456, 789, int(time()), 79)
# s.set_certificate(get_md5(s))
# print(str(s))
# st = Node(None, 234).parse_scrip(str(s))
# print(st)


#===============================================================================
# Products
#===============================================================================
class Product:
    pass
#     __name = ""
#     __price = ""
#     def set_values(name, price):
#         __name = name
#         __price = price
#     name = __name
#     price = __price    

class Book(Product):
    name = "book"
    price = "104" # in cents
    
class Track(Product):
    name = "track"
    price = "99" # in cents
    
class Service(Product):
    name = "service"
    price = "5"  # in cents               