from flask import Flask, request, Response, Response, redirect, url_for
import africastalking
import os
import urllib3
from urllib.parse import urlencode
import json
import re
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

from flask_admin import Admin, BaseView, expose
# from flask_admin.contrib.dictview import DictModelView


app = Flask(__name__)
#Admin view
class ReminderView(BaseView):
    @expose('/')
    def index(self):
        # Here you would typically retrieve and display the reminder data
        return self.render('admin/admin.html', reminder_data=reminder_data)

    @expose('/delete/<session_id>', methods=('POST',))
    def delete_reminder(self, session_id):
        # Delete a specific reminder by session_id
        reminder_data.pop(session_id, None)
        # Redirect to the admin index page after deletion
        return redirect(url_for('.index'))

admin = Admin(app, name='Reminder Admin', template_mode='bootstrap3')

admin.add_view(ReminderView(name='Reminders'))

username = "sandbox"
api_key = "8bdbbcd086033addbe8312b62f44f7daf982220d7c8d4ab09e7f761e4cb2824f"

# Initialize the AfricasTalking services
africastalking.initialize(username, api_key)
sms = africastalking.SMS

# Dictionary to store user input
user_data = {}

# Dictionary to store scheduled reminders
reminder_data = {}

# Define the USSD callback endpoint
@app.route('/', methods=['POST', 'GET'])
def ussd_callback():
    global response
    session_id = request.values.get("sessionId", None)
    text = request.values.get("text", "default")

    # Get the current stage of input for the session
    current_stage = user_data.get(session_id, {}).get('stage', 'medicine_input')

    # Implement logic to handle USSD session based on the user's input
    if text == '':
        user_data.pop(session_id, None)
        # Initial prompt when the user starts the USSD session
        response = "CON Welcome to Reminder App. Follow the instructions to set a reminder:\n"
        response += "1. Continue\n"
        response += "2. Cancel"
    elif '1' in text:
        # User chose to continue, call the handle_input function
        response = handle_input(session_id, current_stage, text)
    elif '2' in text:
        user_data.pop(session_id, None)
        # User chose to cancel, provide a message and end the USSD session
        response = "END Operation canceled."
    else:
        # Invalid input, prompt again
        response = "CON Invalid input. Please follow the instructions."
    return response

@app.route('/delivery-reports', methods=['POST'])
def delivery_reports():
    data = request.get_json(force=True)
    print(f'Delivery report response...\n ${data}')
    return Response(status=200)

@app.route('/sms_callback', methods=['POST'])
def sms_callback(message, recipient):
    send_sms(message, recipient, username, api_key)

def ordinal(n):
    """
    Returns the ordinal suffix for a given number.
    """
    suffix = ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th']
    if 10 <= n % 100 <= 20:
        return str(n) + 'th'
    return str(n) + suffix[n % 10]

def handle_input(session_id, current_stage, text):
    """
    Handles user input based on the current stage of the USSD session.
    """
    # Initialize user_data for the current session if it doesn't exist
    user_data.setdefault(session_id, {})
    
    # Handle input based on the current stage
    if current_stage == 'medicine_input':
        # Set the stage to 'medicine' for the current session
        user_data[session_id]['stage'] = 'medicine'
        # Prompt the user for medicine
        response = "CON Enter the medicine to be taken:"
        text = ""

    elif current_stage == 'medicine':
        print(text)
        medicine = text.split('*')[-1]
        # Save the medicine entered by the user
        user_data[session_id]['medicine'] = medicine
        print(medicine)
        # Set the stage to 'time_choice' for the current session
        user_data[session_id]['stage'] = 'time_choice'
        # Prompt the user for the time
        response = "CON Choose the number of times the medicine is to be taken\n"
        response += "1. Once\n"
        response += "2. Twice\n"
        response += "3. Thrice\n"
        response += "4. Four times a day"
        

    elif current_stage == 'time_choice':
        choice = text.split('*')[-1]
        # Check if the input is a valid option
        if "1" in choice:
            user_data[session_id]['time_choice'] = 1
            user_data[session_id]['stage'] = 'time_once'
            response = "CON Enter the time to take the medicine (e.g., 4:00 PM):"
            
        elif "2" in choice:
            user_data[session_id]['time_choice'] = 2
            user_data[session_id]['stage'] = 'time_twice_1'
            response = "CON Enter the first time to take the medicine (e.g., 4:00 PM):"
        elif "3" in choice:
            user_data[session_id]['time_choice'] = 3
            user_data[session_id]['time_thrice'] = []  # Initialize an empty list to store the times
            user_data[session_id]['stage'] = 'time_thrice_1'
            response = "CON Enter the first time to take the medicine (e.g., 4:00 PM):"
        elif "4" in choice:
            user_data[session_id]['time_choice'] = 4
            user_data[session_id]['time_four'] = []  # Initialize an empty list to store the times
            user_data[session_id]['stage'] = 'time_four_1'
            response = "CON Enter the first time to take the medicine (e.g., 4:00 PM):"
        else:
            # If the input is not valid, prompt the user to choose again
            response = "CON Please choose a valid option (1, 2, 3, or 4) for the number of times the medicine is to be taken."
    elif current_stage == 'time_once':
        print(text)
        time = text.split('*')[-1]
        print(time)
        # Validate the time input
        time_pattern = r'^(0?[1-9]|1[0-2]):[0-5][0-9] ?(AM|PM)$'
        if re.match(time_pattern, time, re.IGNORECASE):
            user_data[session_id]['time_once'] = time
            user_data[session_id]['stage'] = 'animal'
            response = "CON Enter the name of the animal:"
        else:
            response = "CON Invalid time format. Please enter the time in the format HH:MM AM/PM (e.g., 4:00 PM)."
    elif current_stage.startswith('time_twice_'):
        response = handle_multiple_times(session_id, current_stage, text, 2)

    elif current_stage.startswith('time_thrice_'):
        response = handle_multiple_times(session_id, current_stage, text, 3)
        
    elif current_stage.startswith('time_four_'):
        response = handle_multiple_times(session_id, current_stage, text, 4)
            
    elif current_stage == 'animal':
        # Save the name of the animal entered by the user
        animal = text.split('*')[-1]
        print(animal)
        user_data[session_id]['animal'] = animal

        # Set the stage to 'start_date' for the current session
        user_data[session_id]['stage'] = 'start_date'
        # Prompt the user for the start date
        response = "CON Enter the start date for the reminder (YYYY-MM-DD):"
        

    elif current_stage == 'start_date':
        # Validate the start date
        start_date = text.split('*')[-1]
        print(start_date)
        if validate_date(start_date):
            user_data[session_id]['start_date'] = start_date

            # Set the stage to 'end_date' for the current session
            user_data[session_id]['stage'] = 'end_date'
            # Prompt the user for the end date
            response = "CON Enter the end date for the reminder (YYYY-MM-DD):"
            
        else:
            response = "CON Invalid date format. Please enter the date in the format YYYY-MM-DD."

    elif current_stage == 'end_date':
        # Validate the end date
        end_date = text.split('*')[-1]
        print(end_date)
        if validate_date(end_date):
            user_data[session_id]['end_date'] = end_date

            # Set the stage to 'confirmation' for the current session
            user_data[session_id]['stage'] = 'confirmation'
            # Display the entered details and ask for confirmation
            response = generate_confirmation_message(session_id)
            
        else:
            response = "CON Invalid date format. Please enter the date in the format YYYY-MM-DD."

    elif current_stage == 'confirmation':
        # Handle confirmation input
        confirmation_choice = text.split('*')[-1]
        print(confirmation_choice)
        if '1' in confirmation_choice:
            # Save data to storage
            save_data_to_storage(session_id)
            schedule_reminders(session_id)
            response = "END Reminder saved successfully."
        elif '2' in confirmation_choice:
            # User chose to cancel, provide a message and end the USSD session
            user_data.pop(session_id, None)
            response = "END Operation canceled."
        else:
            # Invalid input, prompt again
            response = "CON Invalid input. Please enter 1 to confirm or 2 to cancel."

    return response

def handle_multiple_times(session_id, current_stage, text, max_times):
    """
    Handles input for multiple time entries (e.g., twice, thrice, four times a day).
    """
    time_pattern = r'^(0?[1-9]|1[0-2]):[0-5][0-9] ?(AM|PM)$'
    time_index = int(current_stage.split('_')[-1])
    time_key = '_'.join(current_stage.split('_')[:-1])

    # Initialize the time list if it's not already present
    if time_key not in user_data[session_id]:
        user_data[session_id][time_key] = []

    time = text.split('*')[-1]

    # Validate the time input and process accordingly
    if re.match(time_pattern, time, re.IGNORECASE):
        user_data[session_id][time_key].append(time)
        if time_index < max_times:
            # Move to the next time input
            next_stage = f'{time_key}_{time_index + 1}'
            user_data[session_id]['stage'] = next_stage
            response = f"CON Enter the {ordinal(time_index + 1)} time to take the medicine (e.g., 4:00 PM):"
        else:
            # All times have been entered, move to the next stage
            user_data[session_id]['stage'] = 'animal'
            response = "CON Enter the name of the animal:"
    else:
        response = "CON Invalid time format. Please enter the time in the format HH:MM AM/PM (e.g., 4:00 PM)."
    
    return response

def validate_date(date_str):
    """
    Validates if the given string represents a valid date in the format YYYY-MM-DD.
    """
    try:
        year, month, day = map(int, date_str.split('-'))
        # Add any additional validation rules if needed
        if month < 1 or month > 12:
            return False
        if day < 1:
            return False
        if month in [1, 3, 5, 7, 8, 10, 12]:
            if day > 31:
                return False
        elif month in [4, 6, 9, 11]:
            if day > 30:
                return False
        elif month == 2:
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                if day > 29:
                    return False
            else:
                if day > 28:
                    return False
        return True
    except ValueError:
        return False

def generate_confirmation_message(session_id):
    """
    Generates the confirmation message for the user based on the entered details.
    """
    time_choices = []
    time_choice_keys = ['time_once', 'time_twice', 'time_thrice', 'time_four']
    for key in time_choice_keys:
        if key in user_data[session_id]:
            time_choices.append(user_data[session_id][key])

    # Construct the confirmation message
    confirmation_message = "CON Confirm:\n"
    confirmation_message += f"Medicine: {user_data[session_id].get('medicine', 'Not provided')}\n"

    # If time choices exist, include them in the confirmation message
    if time_choices:
        confirmation_message += "Times:\n"
        if len(time_choices) == 1:
            confirmation_message += f"1. {time_choices[0]}\n"
        else:
            for index, time_choice in enumerate(time_choices, start=1):
                confirmation_message += f"{index}. {time_choice}\n"

    confirmation_message += f"Animal: {user_data[session_id].get('animal', 'Not provided')}\n"
    confirmation_message += f"Start Date: {user_data[session_id].get('start_date', 'Not provided')}\n"
    confirmation_message += f"End Date: {user_data[session_id].get('end_date', 'Not provided')}\n"
    confirmation_message += "1. Confirm\n2. Cancel"

    return confirmation_message

def save_data_to_storage(session_id):
    """
    Saves the user input data to the reminder_data dictionary.
    """
    # Extract data from user_data
    medicine = user_data[session_id]['medicine']
    animal = user_data[session_id]['animal']
    start_date = user_data[session_id]['start_date']
    end_date = user_data[session_id]['end_date']

    time_choices = []
    time_choice_keys = ['time_once', 'time_twice', 'time_thrice', 'time_four times']
    for key in time_choice_keys:
        if key in user_data[session_id]:
            time_choices.append(user_data[session_id][key])

    # Create a dictionary to represent the reminder
    reminder = {
        'medicine': medicine,
        'time': time_choices,
        'animal': animal,
        'start_date': start_date,
        'end_date': end_date,
    }
    reminder_data[session_id] = reminder
    print(reminder)

def schedule_reminders(session_id):
    """
    Schedules reminders based on the user input.
    """
    reminder = reminder_data[session_id]
    start_date = datetime.strptime(reminder['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(reminder['end_date'], '%Y-%m-%d')

    # Convert time strings to datetime objects
    time_choices = [convert_time_to_datetime(time_str) for time_str in reminder['time']]

    # Schedule reminders for each date and time combination
    while start_date <= end_date:
        for time_choice in time_choices:
            scheduled_time = datetime.combine(start_date.date(), time_choice.time())
            schedule_reminder(reminder, scheduled_time)
        start_date += timedelta(days=1)

def convert_time_to_datetime(time_str):
    """
    Converts a time string (e.g., "4:00 PM") to a datetime object.
    """
    hour, minute_meridian = time_str.split(':')
    minute, meridian = minute_meridian.split()
    meridian = meridian.upper()
    hour = int(hour)
    minute = int(minute)
    if meridian == 'PM' and hour != 12:
        hour += 12
    elif meridian == 'AM' and hour == 12:
        hour = 0
    return datetime(1, 1, 1, hour, minute)

def convert_list_of_times_to_datetimes(list_of_time_strs):
    """
    Converts a list of time strings to a list of datetime objects.
    """
    datetimes = []
    for time_str in list_of_time_strs:
        datetimes.append(convert_time_to_datetime(time_str))
    return datetimes

# Creating the scheduler instance
scheduler = BackgroundScheduler()

def schedule_reminder(reminder, scheduled_time):
    """
    Schedules a reminder for a specific date and time.
    """
    #The message for the reminder
    message = f"Don't forget to give {reminder['medicine']} to {reminder['animal']} at {scheduled_time.strftime('%I:%M %p')}."
    def send_reminder_sms():
        recipients = "+254759670554"  # Recipient's number
        # sms_callback()   # Callback function that sends SMS
        # response_to_sms(message, recipients, username, api_key)
        # if response["status"] == "error":
        #     print("Failed to send SMS:", response["description"])
        # else:
        #     print("SMS sent successfully:", response)
        # response_to_sms(message, recipients, username, api_key)
        print(f"Reminder scheduled for {scheduled_time}: {message}")
        sms_callback(message, recipients)
        
    # Schedule the reminder using APScheduler
    scheduler.add_job(send_reminder_sms, 'date', run_date=scheduled_time)
#start the scheduler
scheduler.start()

def send_sms(message, recipients, username, api_key):
    try:
        # Define the endpoint URL
        url = "https://api.sandbox.africastalking.com/version1/messaging"

        # Create an HTTP pool manager
        http = urllib3.PoolManager()

        # Define the headers
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "apiKey": api_key,
        }

        # Construct the payload data
        payload = {
            "username": username,
            "to": recipients,
            "message": message,
            "from": "10357"
        }
        # Encode the payload data
        encoded_payload = urlencode(payload)

        # Make the HTTP POST request
        # response = requests.post(url, headers=headers, data=payload)
        response = http.request("POST", url, body=encoded_payload, headers=headers)

        # Check the response status
        if response.status == 201:
            data = json.loads(response.data.decode("utf-8"))
            print("SMS sent successfully:", data) #response.json()
            return data #response.json()
        else:
            print("Failed to send SMS:", response.data) #response.text
            return {"status": "error", "description": response.data.decode("utf-8")} #response.text
    except Exception as e:
        print(f"We have a problem: {e}")
        return {"status": "error", "description": str(e)}
if __name__ == "__main__":
    app.run(host="0.0.0.0",port=os.environ.get("PORT"),debug=True)
    
