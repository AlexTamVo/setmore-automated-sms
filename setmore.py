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

#Setup twilio
account_sid = "{}".format(data['twilio']['account_sid'])
auth_token = "{}".format(data['twilio']['auth_token'])
client = Client(account_sid, auth_token)

# Setup setmore API token
def access_token():
    response = requests.get("https://developer.setmore.com/api/v1/o/oauth2/token?refreshToken={}".format(data['setmore']['refresh_token']))
    access_token = response.json()['data']['token']['access_token']
    header = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {}" .format(access_token)
    }
    return header

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
            today = datetime.date.today().strftime("%d-%m-%Y")
            setmore_key = requests.get("https://developer.setmore.com/api/v1/bookingapi/appointments?startDate={}&endDate={}&customerDetails=true" .format(today, today), headers = access_token())
            try:
                for x in range(len(setmore_key.json()['data']['appointments'])):
                    try:
                        setmore_num = {'cell_phone':setmore_key.json()['data']['appointments'][x]['customer']['cell_phone']}
                        if setmore_num["cell_phone"] == twilio_num:
                            label = setmore_key.json()['data']['appointments'][x]['label']
                            #Cancels appointment
                            if label != "Cancelled":
                                print("Cancelling appointment for {}".format(twilio_num))
                                if switch == False:
                                    resp.message("Your appointment has been cancelled, if you believe this was a mistake please call 604-588-8667.")
                                    switch = True
                                requests.put("https://developer.setmore.com/api/v1/bookingapi/appointments/{}/label" .format(setmore_key.json()['data']['appointments'][x]['key']), params = {"label": "Cancelled"}, headers = access_token())
                    except:
                        #Pass exception when the appointment has no phone number
                        pass
            except:
                #Pass exception when the appointment has been deleted at the same time - Does not affect functionality
                pass
        elif "bag" in message_body.lower():
            resp.message("If you're getting nail extensions (fake nails) we will charge $3 for a new file and buffer. This bag will be yours to keep for future appointments!")
        elif "confirm" in message_body.lower():
            switch = False
            today = datetime.date.today().strftime("%d-%m-%Y")
            setmore_key = requests.get("https://developer.setmore.com/api/v1/bookingapi/appointments?startDate={}&endDate={}&customerDetails=true" .format(today, today), headers = access_token())
            #Need to add forloop and match twilio_num to appointments (done)
            try:
                for x in range(len(setmore_key.json()['data']['appointments'])):
                    try:
                        #Dictionary was the only way to compare these values together on line 75
                        setmore_num = {'cell_phone':setmore_key.json()['data']['appointments'][x]['customer']['cell_phone']}
                        if setmore_num["cell_phone"] == twilio_num:
                            label = setmore_key.json()['data']['appointments'][x]['label']
                            if label != "Confirmed" and label != "Cancelled" and switch == False:
                                resp.message('''Thank you! Reminder that we charge for a new bag, unsure what that means? Reply with, "bag"\n Book with us again at:\nfusionbeauty.setmore.com/services''')
                                switch = True
                            if label == "Cancelled" and switch == False:
                                resp.message("You have already cancelled your appointment, please call 604-588-8667 to resolve this issue.")
                                switch = True
                            if label == "No Label":
                                requests.put("https://developer.setmore.com/api/v1/bookingapi/appointments/{}/label" .format(setmore_key.json()['data']['appointments'][x]['key']), params = {"label": "Confirmed"}, headers = access_token())
                    except:
                        #Pass exception for when the appointment has no cell phone number
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
        appointments = requests.get("https://developer.setmore.com/api/v1/bookingapi/appointments?startDate={}&endDate={}&customerDetails=true" .format(today, today), headers = access_token())
        print("Sending out notifications! at {}.".format(today))

        #Forloop through appointments
        for x in range(len(appointments.json()['data']['appointments'])):
            time = appointments.json()['data']['appointments'][x]['start_time'].split("T", 1)[1][:-1]
            time = datetime.datetime.strptime(time, "%H:%M").strftime("%I:%M %p")
            try:
                message = client.messages.create(
                    body = 'Fusion Beauty: Your appointment is at {}, reply with, "confirm" to confirm, or, "drop" to cancel it. To stop receiving messages reply with, "cancel".'.format(time),
                    from_ = "{}".format(data['twilio']['phone_num']),
                    to = "+1{}".format(appointments.json()['data']['appointments'][x]['customer']['cell_phone']),
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