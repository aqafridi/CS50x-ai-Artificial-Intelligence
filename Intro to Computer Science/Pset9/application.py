import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # get stockfolio from database
    stockfolio = db.execute("SELECT symbol, SUM(quantity) AS Shares FROM stockfolio WHERE user_id = :user_id \
                            GROUP BY symbol", user_id=session["user_id"])

    shares = []
    value = 0

    # iterate through the stockfolio and add price and total to the dictionarys
    for stock in stockfolio:
        if stock.get("quantity") == 0:
            continue
        quote = lookup(stock.get("symbol"))
        price = quote.get("price")
        name = quote["name"]
        total = price * stock.get("Shares")
        stock["Name"] = name
        stock["Price"] = usd(price)
        stock["Total"] = usd(total)
        shares.append(stock)
        value += round(total, 2)

    # get current cash amount
    rows = db.execute("SELECT cash FROM users WHERE id=:id", id=session['user_id'])
    cash = rows[0]["cash"]

    # calculate total of cash and stock value
    grand_total = value + cash

    return render_template("index.html", shares=shares, cash=usd(cash), value=usd(value), grand_total=usd(grand_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Store the dictionary returned from the search
        symbol = lookup(request.form.get("symbol"))

        # Store the shares inputed and cast into integer
        shares = int(request.form.get("shares"))

        # If the symbol searched is invalid, return apology
        if not symbol:
            return apology("Symbol not found", 400)
        elif shares == float or shares < 1:
            return apology("Share must be non-negative and numeric", 400)

        # Calculate cost of transaction
        cost = int(request.form.get("shares")) * symbol['price']

        # Check if user has enough cash to buy the shares
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session['user_id'])
        if cost > cash[0]["cash"]:
            return apology("Sorry, you don't have enough cash to buy these shares.")

        # update cash amount in users database
        updated_cash = cash[0]["cash"] - shares * symbol['price']
        db.execute("UPDATE users SET cash=:updated_cash WHERE id=:user_id", updated_cash=updated_cash, user_id=session["user_id"])

        # add transaction to user's history
        db.execute("INSERT INTO history (user_id, symbol, price, shares, date, transaction_type) VALUES (:user_id, :symbol, :price, :shares, :date, 'BUY')",
                   user_id=session["user_id"], symbol=symbol['symbol'], price=symbol['price'], shares=shares, date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # alert user of the newly bought shares
        flash('Successfully bought!')

        # obtain number of shares of symbol in portfolio
        current_stockfolio = db.execute("SELECT quantity FROM stockfolio WHERE symbol=:symbol", symbol=symbol["symbol"])

        # if symbol is new, add to stockfolio
        if not current_stockfolio:
            db.execute("INSERT INTO stockfolio (user_id, symbol, quantity) VALUES (:user_id, :symbol, :quantity)",
                       user_id=session["user_id"], symbol=symbol['symbol'], quantity=int(request.form.get("shares")))

        # if symbol is already in portfolio, update quantity of shares and total
        else:
            db.execute("UPDATE stockfolio SET quantity=quantity+:quantity WHERE symbol=:symbol",
                       quantity=int(request.form.get("shares")), symbol=symbol["symbol"])

        return redirect("/")

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Query history
    transacted = db.execute(
        "SELECT transaction_type, symbol, price, date, shares FROM history WHERE user_id = :user_id", user_id=session["user_id"])

    # Iterate over the stocks list to add information needed in history.html
    for stock in transacted:
        symbol = str(stock["symbol"])
        name = lookup(symbol)["name"]
        stock["name"] = name

    return render_template("history.html", transacted=transacted)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Alert of successful login
        flash('Successfully Logged In!')

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Store the dictionary returned from the search
        symbol = lookup(request.form.get("symbol"))

        # If the symbol searched is invalid, return apology
        if not symbol:
            return apology("Symbol not found", 400)

        # If the symbol exists, return the search
        else:
            return render_template("quoted.html", name=symbol["name"], symbol=symbol["symbol"], price=usd(symbol["price"]))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password and confirmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 400)

        # Query database for username
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        try:
            newuser = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                                 username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")))
        except:
            return apology("username is already registered", 400)

        # Start session
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Store the dictionary returned from the search
        symbol = lookup(request.form.get("symbol"))

        # Store the shares inputed and cast into integer
        shares = int(request.form.get("shares"))

        # If the symbol searched is invalid, return apology
        if not symbol:
            return apology("Symbol not found", 400)

        # Calculate cost of transaction
        cost = int(request.form.get("shares")) * symbol['price']

        # Check if user has enough quantity of the shares to sell
        current_shares = db.execute("SELECT symbol, SUM(quantity) as totalshares FROM stockfolio WHERE user_id=:user_id GROUP BY symbol HAVING totalshares > 0",
                                    user_id=session["user_id"])

        for row in current_shares:
            if shares > row['totalshares']:
                return apology("You cannot sell more shares than you currently hold.")

        # obtain current cash amount from database
        rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session['user_id'])
        cash = rows[0]['cash']

        # update cash amount in users database
        updated_cash = cash + shares * symbol['price']
        db.execute("UPDATE users SET cash=:updated_cash WHERE id=:user_id", updated_cash=updated_cash, user_id=session["user_id"])

        # add transaction to user's history
        # If the user is selling all the shares, remove the stock from the user's portfolio
        db.execute("INSERT INTO history (user_id, symbol, price, shares, date, transaction_type) VALUES (:user_id, :symbol, :price, :shares, :date, 'SELL')",
                   user_id=session["user_id"], symbol=symbol['symbol'], price=symbol['price'], shares=-1 * shares, date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # alert user of the newly bought shares
        flash('Successfully sold!')

        # pull number of shares of symbol in portfolio
        current_stockfolio = db.execute("SELECT quantity FROM stockfolio WHERE symbol=:symbol", symbol=symbol["symbol"])

        # update quantity of shares and total
        db.execute("UPDATE stockfolio SET quantity=quantity-:quantity WHERE symbol=:symbol",
                   quantity=int(request.form.get("shares")), symbol=symbol["symbol"])

        return redirect("/")

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        symbols = db.execute("SELECT symbol FROM stockfolio WHERE user_id=:user_id GROUP BY symbol HAVING SUM(quantity) > 0",
                             user_id=session["user_id"])

        return render_template("sell.html", symbols=symbols)


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Add cash to user's account"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # update cash by requested amount in add_cash.html
        db.execute("UPDATE users SET cash = cash + :additional WHERE id = :user_id",
                   additional=request.form.get('cash'), user_id=session["user_id"])

        flash('Additional Cash Added!')
        return redirect("/")

    else:
        return render_template("add_cash.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
