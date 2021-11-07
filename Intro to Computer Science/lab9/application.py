import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///birthdays.db")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        # Obtain data from form
        name = request.form.get("name")
        month = request.form.get("month")
        day = request.form.get("day")

        # Add the user's entry into the database
        db.execute(" INSERT INTO birthdays (name, month, day) VALUES (?, ?, ?)", name, month, day)

        # Redirect to home
        return redirect("/")

    else:
        # Query for all birthdays
        birthday = db.execute("SELECT * FROM birthdays")

        # Update bithday page with the info
        return render_template("index.html", birthdays = birthday)