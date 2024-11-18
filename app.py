#importing the necessary packages
from flask import Flask,request,jsonify
import json
from datetime import datetime
from functools import wraps
import threading
from enum import Enum

#class enum for status
class Status(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
#used for avoid data colloide  between reading and writing of json file
data_lock = threading.Lock()

app=Flask(__name__)

def read_task_data():
    with data_lock:
        try:
            with open('data.json', 'r') as f:
                return json.load(f) or []
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            return []

def write_task_data(data):
    with data_lock:
        with open('data.json', 'w') as f:
            json.dump(data, f)



#username and password for authorisation
Auth_data={
    "admin":1234, #username-> admin password ->1234
}

#variable to store Task Data
task_data = {}

# function to verify the Password
def verify_credentials(username,password):
    return Auth_data[username]==int(password)

#function for creating Response to send to user
def create_response(message, data=None, status=200):
    if data:
        return jsonify({"message": message, "data": data}), status
    else:
        return jsonify({"message": message}), status

# decorator for authentication
def authenticate(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization  # Get the Authorization header
        if not auth or not verify_credentials(auth.username, auth.password):
            return jsonify({"message": "Authentication required"}), 401, {
                'WWW-Authenticate': 'Basic realm="Login Required"'
            }
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
@authenticate
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Task Management API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                margin: 0;
                padding: 0;
                background-color: #f4f4f9;
                color: #333;
            }
            h1 {
                color: #5c6bc0;
                margin-top: 50px;
            }
            p {
                margin-top: 20px;
                font-size: 18px;
            }
            a {
                color: #5c6bc0;
                text-decoration: none;
                font-weight: bold;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <h1>Welcome to Task Management REST API Project</h1>
        <p>This API allows you to manage tasks efficiently.</p>
        <p>Explore the <a href="">API Documentation</a> to get started!</p>
    </body>
    </html>
    """
    return html_content

@app.route("/tasks",methods=["POST","GET"])
@authenticate
def getTasks():
    task_data = read_task_data()

    #handing the GET method
    if request.method=="GET":
        
        # Handling filter conditions
        status = request.args.get("status")  
        title = request.args.get("title")   
        due_date = request.args.get("due_date")  

        filtered_tasks = task_data

        if status:
            filtered_tasks = [
                task for task in filtered_tasks if task["status"].lower() == status.lower()
            ]
        if title:
            filtered_tasks = [
                task for task in filtered_tasks if title.lower() in task["title"].lower()
            ]
        if due_date:
            try:
                due_date_filter = datetime.fromisoformat(due_date)
                filtered_tasks = [
                    task for task in filtered_tasks if datetime.fromisoformat(task["due_date"]) <= due_date_filter
                ]
            except ValueError:
                return create_response("Invalid date format. Use YYYY-MM-DD", status=400) 
            
        #returning the data after filter    
        return jsonify(filtered_tasks), 200
    
    #handing the POST method
    if request.method =="POST":
        try:
            receieved_data= request.get_json()
            
            if not receieved_data:
                return create_response("Please enter valid data", status=400)
            
            #Verifying whether all Fields are there or not
            required_fields = ["id", "title", "description", "status"]
            for field in required_fields:
                if not receieved_data.get(field):
                    return create_response(f"Please enter {field.capitalize()}", status=400)
                
            #validating the id whether it is already present or not
            id = receieved_data.get("id")
            duplicate = [t for t in task_data if t.get("id")==id]
            if duplicate:
                return create_response ("Duplicate Task id Found! Please Enter other Task id.",status=400)

            #validating due date
            try:
                due_date = datetime.fromisoformat(receieved_data["due_date"])
                if due_date<datetime.now():
                    return create_response("Due Date Must be in the Future", status=400)
            except KeyError:
                return create_response("Missing required data", status=400)
            except Exception as e:
                return create_response("An unexpected error occurred: {str(e)}", status=400)
            
            #validating status
            try:
                status = Status[receieved_data["status"].upper()]
            except KeyError:
                return create_response("Please enter valid Status", status=400)

            valid_data = {
                "id" : receieved_data["id"],
                "title":receieved_data["title"],
                "description":receieved_data["description"],
                "due_date":receieved_data["due_date"],
                "status":status.value,
                "created_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            task_data.append(valid_data)

            #writing to json file
            write_task_data(task_data)

            return create_response("SuccessFully Added")
        except:
            return create_response("Invalid Json", status=400)
        
@app.route("/tasks/<id>/complete",methods=["PATCH"])
@authenticate
def MarkasComplete(id):
    try:
        #reading the json file for updated task data
        task_data = read_task_data()
        
        Task_To_Patch = next((task for task in task_data if task["id"]==int(id)),None)
        if Task_To_Patch :
            #changing the status to completed
            Task_To_Patch["status"]="completed"
            Task_To_Patch["updated_at"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            #writing list back to the json file
            write_task_data(task_data)
            return create_response("Sussessfully Marked as completed")
        else:
            #if the corresponding TASK id not found, throwing and error message
            return create_response(f"Task {id} Not Found",status=400)
    except ValueError:
        return create_response("Invalid ID format", status=400)
    except Exception as e:
        return create_response(f"An error occurred: {str(e)}", status=500)



@app.route("/tasks/<id>",methods=["GET","PUT","DELETE"])
@authenticate
def getTask(id):
    try:
        #reading the json file for updated task data
        task_data = read_task_data()
        task = next((task for task in task_data if task["id"] == int(id)), None)

        if request.method == "GET":
            if task:
                #returning the success message and task data
                return create_response("Task retrieved successfully", task)
            return create_response("Task not found", status=404)

        if request.method == "DELETE":
            #checking whether task is not null
            if task:
                #copying all values except the current id values
                task_data = [t for t in task_data if t["id"] != int(id)]

                #updating back to the json file
                write_task_data(task_data)
                
                #returning the success message and task data
                return create_response("Task deleted successfully", task)
            #returning error response if TASK id is not valid
            return create_response(f"TASK {id} not found", status=404)
        
        if request.method=="PUT":
            #reading the request body in json format
            receieved_data = request.get_json()

            #validating the input data, whether null or not
            if not receieved_data:
                #returning error response if the input data is null
                return create_response("Please enter valid data",status=400)
            
            #checking for all the fields, whether input json consists or not
            required_fields = ["title", "description", "status"]
            for field in required_fields:
                if not receieved_data.get(field):
                    #if the json does not consists any field returning error message
                    return create_response(f"Please enter valid {field.capitalize()}",status=400)
            
            #validating the input data  
            try:
                due_date = datetime.fromisoformat(receieved_data["due_date"])
                if due_date<datetime.now():
                    return create_response("Due Date Must be in the Future",status=400)
            except KeyError:
                return create_response( "Missing required data",status= 400)
            except Exception as e:
                return create_response( f"An unexpected error occurred: {str(e)}", status=500)

            try:
                status = Status[receieved_data["status"].upper()]
            except KeyError:
                return create_response("Please enter valid Status",status=400)

            existing_data = next((task for task in task_data if task["id"]==int(id)),None)

            #if the id entered by user is not available then creating a new Task and inserting that value
            if not existing_data:
                valid_data = {
                    "id":int(id),
                    "title":receieved_data["title"],
                    "description":receieved_data["description"],
                    "due_date":receieved_data["due_date"],
                    "status":status.value,
                    "created_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                task_data.append(valid_data)
                write_task_data(task_data)
                return create_response("Success",valid_data)
        
            else:
                #if the id entered by user is available then field will be updated
                existing_data["title"] = receieved_data["title"]
                existing_data["description"] = receieved_data["description"]
                existing_data["due_date"] = receieved_data["due_date"]
                existing_data["status"] = receieved_data["status"]

                #updating the updated_at using current datetime
                existing_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                #updating task data in Json file
                write_task_data(task_data)

            return create_response("Success",existing_data)
    except ValueError:
        return create_response("Invalid ID format", status=400)
    except Exception as e:
        return create_response(f"An error occurred: {str(e)}", status=500)

#main program starts here
if __name__ == "__main__":
    app.run(debug=True)