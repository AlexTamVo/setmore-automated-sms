from os import access
import requests
import datetime
import json
import threading
import multiprocessing
from schedule import every, repeat, run_pending
import time
from tkinter import *
from twilio.rest import Client
from flask import Flask, request, redirect
from twilio.twiml.messaging_response import Message, MessagingResponse

#config file
with open("config/config.json") as json_data_file:
    data = json.load(json_data_file)

#Generate new access token every 5 minutes, due to API rate limits 
@repeat(every(5).minutes)
def refresh_token():
    response = requests.get("https://developer.setmore.com/api/v1/o/oauth2/token?refreshToken={}".format(data['setmore']['refresh_token']))
    
    return response

#Setup twilio
account_sid = "{}".format(data['twilio']['account_sid'])
auth_token = "{}".format(data['twilio']['auth_token'])
client = Client(account_sid, auth_token)
response = refresh_token()

#Get API headers with access token
def access_token():
    access_token = response.json()['data']['token']['access_token']
    header = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {}" .format(access_token)
    }

    return header

#functions for interacting with setmore's API
def get_appointments():
    today = datetime.date.today().strftime("%d-%m-%Y")
    setmore_key = requests.get("https://developer.setmore.com/api/v1/bookingapi/appointments?startDate={}&endDate={}&customerDetails=true" .format(today, today), headers = access_token())
    setmore_appointments = setmore_key.json()['data']['appointments']

    return setmore_appointments

def get_key():
    today = datetime.date.today().strftime("%d-%m-%Y")
    setmore_key = requests.get("https://developer.setmore.com/api/v1/bookingapi/appointments?startDate={}&endDate={}&customerDetails=true" .format(today, today), headers = access_token())
    
    return setmore_key

def confirm_appointment(appointment_key):
    requests.put("https://developer.setmore.com/api/v1/bookingapi/appointments/{}/label" .format(appointment_key), params = {"label": "Confirmed"}, headers = access_token())

def cancel_appointment(appointment_key):
    requests.put("https://developer.setmore.com/api/v1/bookingapi/appointments/{}/label" .format(appointment_key), params = {"label": "Cancelled"}, headers = access_token())

#reminder system

def flask():
    app = Flask(__name__)

    @app.route("/sms", methods=["GET", "POST"])
    def sms_reply():
        


        resp = MessagingResponse()
        message_body = request.form['Body']
        twilio_num = request.form['From'].split("+1", 1)[1]


        #log messages sent by client
        print("Message from {}: {}\n".format(twilio_num, message_body))


        if "drop" in message_body.lower():
            switch = False
            setmore_appointments = get_appointments()
            setmore_key = get_key()


            try:
                for x in range(len(setmore_appointments)):
                    try:

                        setmore_num = {'cell_phone':setmore_key.json()['data']['appointments'][x]['customer']['cell_phone']}


                        if setmore_num["cell_phone"] == twilio_num:

                            label = setmore_key.json()['data']['appointments'][x]['label']
                            appointment_key = setmore_key.json()['data']['appointments'][x]['key']

                            #Cancels appointment
                            if label != "Cancelled":
                                print("Cancelling appointment for {}".format(twilio_num))
                                if switch == False:
                                    resp.message("Your appointment has been cancelled, if you believe this was a mistake please call 604-588-8667.")
                                    switch = True
                                cancel_appointment(appointment_key)
                    except:
                        #Phone number doesn't exist in booking info - skip this appointment
                        pass
            except:
                #Exception when appointment is deleted at the same time - doesn't affect program: pass to prevent crash
                pass


        elif "bag" in message_body.lower():
            resp.message("If you're getting nail extensions (fake nails) we will charge $3 for a new file and buffer. This bag will be yours to keep for future appointments!")


        elif "confirm" in message_body.lower():
            switch = False
            setmore_appointments = get_appointments()
            setmore_key = get_key()


            try:
                for x in range(len(setmore_key.json()['data']['appointments'])):
                    try:

                        #Dictionary was the only way to compare these values together on line 108
                        setmore_num = {'cell_phone':setmore_key.json()['data']['appointments'][x]['customer']['cell_phone']}


                        if setmore_num["cell_phone"] == twilio_num:


                            label = setmore_key.json()['data']['appointments'][x]['label']
                            appointment_key = setmore_key.json()['data']['appointments'][x]['key']


                            if label != "Confirmed" and label != "Cancelled" and switch == False:
                                resp.message('''Thank you! Reminder that we charge for a new bag, unsure what that means? Reply with, "bag"\n Book with us again at:\nfusionbeauty.setmore.com/services''')
                                switch = True
                            if label == "Cancelled" and switch == False:
                                resp.message("You have already cancelled your appointment, please call 604-588-8667 to resolve this issue.")
                                switch = True
                            if label == "No Label":
                                confirm_appointment(appointment_key)
                    except:
                        #No phone number associated with this booking - skip sending message
                        pass
            except:
                #Most likely due to a scheduled appointment being deleted at the same time - has no actual effect to program.
                pass


        else:
            resp.message("Sorry! I do not understand that command, if you need assistance please call me.")
            #Sends the unknown command to business number in config.json.
            try:
                message = client.messages.create(
                    body = "Unknown command received from Twilio: \n{}\n\n{}".format(twilio_num, message_body),
                    from_ = "{}".format(data['twilio']['phone_num']),
                    to = "+1{}".format(data['twilio']['business_num'])
                )
            except:
                print("Unknown exception generated from fowarding message to business number. Perhaps the line is down?")
                pass


        return str(resp)
    app.run(debug=False)

@repeat(every().day.at("08:00"))
def send_appointments():
        #Get today's date, initalize other variables
        today = datetime.date.today().strftime("%d-%m-%Y")
        setmore_keys = get_key()
        print("\n\nSENDING OUT NOTIFICATIONS at: {}.".format(today))

        #Forloop through appointments
        for x in range(len(setmore_keys.json()['data']['appointments'])):


            time = setmore_keys.json()['data']['appointments'][x]['start_time'].split("T", 1)[1][:-1]
            time = datetime.datetime.strptime(time, "%H:%M").strftime("%I:%M %p")


            try:
                message = client.messages.create(
                    body = 'Fusion Beauty: Your appointment is at {}, reply with, "confirm" to confirm, or, "drop" to cancel it. To stop receiving messages reply with, "STOP".'.format(time),
                    from_ = "{}".format(data['twilio']['phone_num']),
                    to = "+1{}".format(setmore_keys.json()['data']['appointments'][x]['customer']['cell_phone']),
                )
            except:
                print("Exception generated from sending an appointment reminder - Cause: Deleted appointment or unreachable number.")
                pass


def manual_start():
    while True:
        start = input("Type in, 'start' to manually send out notifications.\n")
        if start == "start":
            print("Notifications successfully sent out")
            send_appointments()


def timer():
    while True: 
        run_pending()
        time.sleep(1)
threading.Thread(target=timer).start()
threading.Thread(target=flask).start()
threading.Thread(target=manual_start).start()