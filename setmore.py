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
        print("Message from {}: {}".format(twilio_num, message_body))
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
                        pass
            except:
                pass
        if "bag" in message_body.lower():
            resp.message("If you're getting nail extensions (fake nails) we will charge $3 for a new file and buffer. This bag will be yours to keep for future appointments!")
        if "confirm" in message_body.lower():
            switch = False
            today = datetime.date.today().strftime("%d-%m-%Y")
            setmore_key = requests.get("https://developer.setmore.com/api/v1/bookingapi/appointments?startDate={}&endDate={}&customerDetails=true" .format(today, today), headers = access_token())
            #Need to add forloop and match twilio_num to appointments (done)
            try:
                for x in range(len(setmore_key.json()['data']['appointments'])):
                    try:
                        setmore_num = {'cell_phone':setmore_key.json()['data']['appointments'][x]['customer']['cell_phone']}
                        if setmore_num["cell_phone"] == twilio_num:
                            label = setmore_key.json()['data']['appointments'][x]['label']
                            if label != "Confirmed" and label != "Cancelled" and switch == False:
                                resp.message('Thank you! Book with us again at:\nfusionbeauty.setmore.com/services\nIf applicable bring a file and buffer. Unsure what that means? Reply with, "bag"')
                                switch = True
                            if label == "Cancelled" and switch == False:
                                resp.message("You have already cancelled your appointment, please call 604-588-8667 to resolve this issue.")
                                switch = True
                            if label == "No Label":
                                requests.put("https://developer.setmore.com/api/v1/bookingapi/appointments/{}/label" .format(setmore_key.json()['data']['appointments'][x]['key']), params = {"label": "Confirmed"}, headers = access_token())
                    except:
                        pass
            except:
                pass
        return str(resp)
    app.run(debug=False)

@repeat(every().day.at("08:00"))
def send_appointments():
        #Get today's date, initalize other variables
        today = datetime.date.today().strftime("%d-%m-%Y")
        appointments = requests.get("https://developer.setmore.com/api/v1/bookingapi/appointments?startDate={}&endDate={}&customerDetails=true" .format(today, today), headers = access_token())
        print("Sending out notifications!")

        #Forloop through appointments
        for x in range(len(appointments.json()['data']['appointments'])):
            time = appointments.json()['data']['appointments'][x]['start_time'].split("T", 1)[1][:-1]
            time = datetime.datetime.strptime(time, "%H:%M").strftime("%I:%M %p")
            try:
                message = client.messages.create(
                    body = 'Fusion Beauty Guildford: Your appointment is at {}, please reply with, "confirm" to confirm your appointment, or, "drop" to cancel it.'.format(time),
                    from_ = "{}".format(data['twilio']['phone_num']),
                    to = "+1{}".format(appointments.json()['data']['appointments'][x]['customer']['cell_phone']),
                )
            except:
                pass
def timer():
    while True:
        run_pending()
        time.sleep(1)
threading.Thread(target=timer).start()
threading.Thread(target=flask).start()