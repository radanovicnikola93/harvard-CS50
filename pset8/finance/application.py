import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    portfolio = db.execute(
        "SELECT symbol, SUM(shares) as shares, price_of_share, cost FROM portfolio WHERE user_id = :user_id GROUP BY symbol", user_id=session["user_id"])

    rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

    cash_available = rows[0]["cash"]

    return render_template("index.html", portfolio=portfolio, cash_available=cash_available)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        # Checking for errors
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Please fill out the form")

        # Search from lookup in helpers.py
        quote = lookup(request.form.get("symbol"))
        shares = int(request.form.get("shares"))

        # Return error if there aren't any symbols found
        if quote == None:
            return apology("Symbol not found")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer")

        # Only positive integers allowed
        if shares <= 0:
            return apology("Only positive quantity")

        # Selecting cash from allocated ID
        rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

        # User cash
        cash = rows[0]["cash"]

        # Cost of the share
        price_of_share = quote["price"]

        # Total cost of buying shares
        cost = price_of_share * shares

        # Return error if user does not have enough cash
        if cost > cash:
            return apology("Sorry, not enough cash")

        # if cash available update users and portfolio database
        else:
            db.execute("UPDATE users SET cash = cash - :price WHERE id = :user_id", price=cost, user_id=session["user_id"])
            db.execute("INSERT INTO portfolio (id, user_id, symbol, price_of_share, cost, shares) VALUES(NULL, :user_id, :symbol, :price_of_share, :cost, :shares)",
                       user_id=session["user_id"], symbol=request.form.get("symbol"), price_of_share=price_of_share, cost=cost, shares=request.form.get("shares"))

        flash("You successfully bouth your share/s")

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    return jsonify("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Selecting all data from database
    history = db.execute(
        "SELECT id, symbol, price_of_share as price, cost, time, shares FROM portfolio WHERE user_id = :user_id GROUP BY id", user_id=session["user_id"])

    return render_template("history.html", history=history)


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

        # Print message if user successfully logged in
        flash('You were successfully logged in')

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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
    if request.method == "POST":
        # If the input is blank give an error
        if not request.form.get("symbol"):
            return apology("Provide a symbol")

        # Search from lookup in helpers.py
        quote = lookup(request.form.get("symbol"))

        # If mispelled return error
        if quote == None:
            return apology("Symbol not found")

        # Return to quoted.html to show current values of the share
        return render_template("quoted.html", quote=quote)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Checking for errors
        if not request.form.get("username"):
            return apology("Please provide a username")
        elif not request.form.get("password"):
            return apology("Please provide a password")
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("Passwords doesn't match")

        # Store password in hashes
        hash_password = generate_password_hash(request.form.get("password"))

        # Storing data in database
        user = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                          username=request.form.get("username"), hash=hash_password)

        # Check if user exists
        if not user:
            return apology("User exists")

        # Print message if the user succesfully registered
        flash('You are successfully registered')

        # Remember user after logging in
        session["user_id"] = user

        # Redirect to main page after registration
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        quote = lookup(request.form.get("symbol"))

        # checking for errors
        if quote == None:
            return apology("Symbol not found")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Must be a number")

        if shares <= 0:
            return apology("Must be a positive number")

        # selecting available shares from portfolio
        stock = db.execute("SELECT SUM(shares) as total_shares FROM portfolio WHERE user_id = :user_id and symbol = :symbol GROUP BY symbol",
                           user_id=session["user_id"], symbol=request.form.get("symbol"))

        # checking for available quantity of shares
        if stock[0]["total_shares"] < 1 or shares > stock[0]["total_shares"]:
            return apology("You don't have this much shares")

        price_of_share = quote["price"]

        # determing total price
        cost = shares * price_of_share

        # updating user cash
        db.execute("UPDATE users SET cash = cash + :price WHERE id = :user_id", user_id=session["user_id"], price=cost)

        # updating user portfolio
        db.execute("INSERT INTO portfolio (id, user_id, symbol, price_of_share, cost, shares) VALUES(NULL, :user_id, :symbol, :price_of_share, :cost, :shares)",
                   user_id=session["user_id"], symbol=request.form.get("symbol"),
                   price_of_share=price_of_share, cost=cost, shares=-shares)

        flash("Share sold!")

        return redirect("/")

    else:
        user_shares = db.execute(
            "SELECT symbol, SUM(shares) as total_shares FROM portfolio WHERE user_id = :user_id GROUP BY symbol", user_id=session["user_id"])

        return render_template("sell.html", user_shares=user_shares)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
