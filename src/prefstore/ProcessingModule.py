"""
Created on 12 April 2011
@author: jog
"""

from new import * #@UnusedWildImport
import json
import base64
import random
import __builtin__
import sys
import DatawareDB
import MySQLdb
import hashlib
import logging

#setup logger for this module
log = logging.getLogger( "console_log" )

#TODO: Still need a logout even when the person hasn't registered (maybe call it cancel?)
#TODO: how to prevent accidental "google logins". Is this you?, etc.
#///////////////////////////////////////////////


class ProcessingModule( object ) :

    #set of commands that are permissable within the sandbox's e
    #excecution environment (list borrowed from the "CAPE" sandbox )
    ALLOWED_BUILTINS = [
        'abs', 'bool', 'callable', 'chr', 'cmp', 'coerce', 'complex', 
        'dict', 'divmod', 'enumerate', 'filter', 'float', 'getattr', 
        'hasattr', 'hash', 'hex', 'int', 'intern', 'isinstance',
        'issubclass', 'iter', 'len', 'list', 'locals', 'long', 'map',
        'max', 'min', 'oct', 'ord', 'pow', 'range', 'reduce', 'repr',
        'round', 'slice', 'str', 'sum', 'tuple', 'type', 'unichr',
        'unicode', 'xrange', 'zip'
    ]
    
    #///////////////////////////////////////////////
    
    
    def __init__( self ):
        self.db = DatawareDB.DatawareDB()
        self.db.connect()
        self.db.checkTables()
        
        self.sandbox_builtins = __builtin__.__dict__.copy()
        
        for command in __builtin__.__dict__ :
            if command not in self.ALLOWED_BUILTINS :
                del self.sandbox_builtins[ command ]
        
        
    
    #///////////////////////////////////////////////
        
        
    def __del__(self):
        if self.db.connected: 
            self.db.close(); 
       
         
    #///////////////////////////////////////////////


    def format_register_success( self, access_token ):
        
        if ( access_token ) :
            json_response = { 'success': True, 'access_token': access_token }
        else : 
            json_response = { 'success': True }
        
        return json.dumps( json_response );
           
         
    #///////////////////////////////////////////////


    def format_register_failure( self, error, msg ):
        
        json_response = { 
            'success': False,
            'error':error,
            'error_description':msg
        } 
        
        return json.dumps( json_response );
          
        
    #///////////////////////////////////////////////
    
    
    def format_process_success( self, result = None ):
        
        if ( result ) :
            json_response = { 'success': True, 'return': result }
        else : 
            json_response = { 'success': True }
        
        return json.dumps( json_response );
    
              
    #///////////////////////////////////////////////


    def format_process_failure( self, error, msg ):
      
        json_response = { 
            'success': False,
            'error':error,
            'error_description':msg
        } 
        
        return json.dumps( json_response );
          
    
     
    #///////////////////////////////////////////////
    
    
    def invoke_request( self, access_token, jsonParams ):
        
        if access_token is None :
            return self.format_process_failure(
                "access_exception",
                "Access token has not been supplied"
            ) 

        try:
            parameters = json.loads( jsonParams ) if jsonParams else {}
        except:
            return self.format_process_failure(
                "access_exception",
                "incorrectly formatted JSON parameters"
            ) 
    
        try:
            request = self.db.fetch_request( access_token )
            if request is None:
                return self.format_process_failure(
                    "access_exception",
                    "Invalid access token"
                )
             
            #obtain relevent info from the request object    
            user = request[ "user_id" ]
            query = request[ "query" ]
                        
        except:
            return self.format_process_failure(
                "access_exception",
                "Database problems are currently being experienced"
            ) 

        try:
            sandbox = self.setup_sandbox( user, query )

        #TODO: Should probably log exceptions like these                           
        except Exception, e:
            return self.format_process_failure(
                "processing_exception",
                "Compile-time failure - %s:%s" % 
                ( type( e ).__name__,  e )
            ) 

        #finally invoke the function
        try:
            result = sandbox.run( parameters )
            return self.format_process_success( result )
        
        #and catch any problems that occur in processing
        except:
           
            return self.format_process_failure(
                "processing_exception",
                "Run-time failure - %s " % str( sys.exc_info() )
            ) 

            
    #///////////////////////////////////////////////
    
    
    def setup_sandbox( self, user, query ) :
        
        #setup sandbox module for running query in
        #TODO: THIS NEEDS A LOT MORE TIGHTENING UP! 
        sandbox = module( "sandbox" )
        #sandbox.__dict__[ '__builtins__' ] = self.sandbox_builtins
        sandbox.db = self.db
        
        #setup constants available to the query
        sandbox.TOTAL_WEB_DOCUMENTS = 2500000000
        sandbox.user = user

        #load the query function into memory
        exec query in sandbox.__dict__
        
        return sandbox
        
            
    #///////////////////////////////////////////////
    
        
    def register_request( self, user_name, 
        client_id, shared_secret, resource_id, query, expiry_time ): 
        
        #check that the shared_secret is correct for this user_id
        try:
            if ( not self.db.authenticate( user_name, shared_secret ) ) :
                return self.format_register_failure(
                    "registration_failure",
                    "incorrect user_id or shared_secret"
                ) 
        except:    
            return self.format_register_failure(
                "registration_failure",
                "Database problems are currently being experienced"
            ) 
        
        #check that the client_id exists and is valid
        if not ( client_id ):
            return self.format_register_failure(
                "registration_failure",
                "A valid client ID has not been provided"
            )  
        
        #check that the requested query is syntactically correct
        try:
            compile( query, '', 'exec' )
        except:
            return self.format_register_failure(
                "registration_failure",
                "Compilation error"
            ) 
            
        #TODO: check that the expiry time is valid
        #TODO: check that the resource_id is correct (i.e. us)
        #TODO: should check code here to confirm that it is valid 
        #TODO: this could be done by comparisng the checksum for acceptable queries?
        #TODO: this will require sandboxing, and all sorts...
       
        #so far so good. Time to generate an access token
        access_token = self.generateAccessToken();
        try:
            self.db.insert_request( 
                access_token, 
                client_id, 
                user_name, 
                expiry_time, 
                query 
            )
                       
            return self.format_register_success(
                { "access_token" : access_token } 
            ) 
        
        #if the user access_token already exists an Integrity Error will be thrown
        except MySQLdb.IntegrityError:
            return self.format_register_failure(
                "registration_failure",
                "An identical request already exists"
            ) 
              
        except:    
            return self.format_register_failure(
                "registration_failure",
                "Database problems are currently being experienced"
            ) 
            
                
    #///////////////////////////////////////////////
    
    
    def deregister_request( self, user_name, shared_secret, access_token ):
 
        #check that the shared_secret is correct for this user_id
        try:
            if not access_token :
                return self.format_register_failure(
                    "deregister_failure",
                    "Identifying access token not supplied"
                ) 
                
            if not self.db.authenticate( user_name, shared_secret ) :
                return self.format_register_failure(
                    "deregister_failure",
                    "Incorrect user_name or shared_secret"
                ) 
    
            if self.db.delete_request( access_token, user_name ) :
                return self.format_register_success() 
            else :
                return self.format_register_failure(
                    "deregister_failure",
                    "Request with that access token could not found"
                ) 
        except:    
            return self.format_register_failure(
                "deregister_failure",
                "Database problems are currently being experienced"
            ) 
            
            
    #///////////////////////////////////////////////

             
    def generateAccessToken( self ):
        
        token = base64.b64encode(  
            hashlib.sha256( 
                str( random.getrandbits(256) ) 
            ).digest() 
        )  
            
        #replace plus signs with asterisks. Plus signs are reserved
        #characters in ajax transmissions, so just cause problems
        return token.replace( '+', '*' ) 

        
    
    