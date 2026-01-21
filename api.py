import uuid, os, requests, random, jwt, datetime
from sqlalchemy import func, or_
from flask import Flask, jsonify, request, current_app, g
from flask_cors import CORS
from dotenv import load_dotenv
from functools import lru_cache, wraps
from flask_jwt_extended import jwt_required, get_jwt_identity, JWTManager, create_access_token
from decimal import Decimal
from models import db, Word, Morpheme, Company, Ownership, SharePrice, User

load_dotenv()
app = Flask(__name__, instance_relative_config=True)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "development-key")
app.config["JWT_SECRET_KEY"] = app.config["SECRET_KEY"] 
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"
CORS(app)
jwt = JWTManager(app)
db.init_app(app)

SUPABASE_PROJECT_ID = "sblovettyyzfrvbiroiz"
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")
START_DATE = datetime.datetime(2025, 9, 1)

filterPattern = {
    "0": [],
    "1": ["general"],
    "2": ["special"],
    "3": ["general", "special"],
    "4": ["replaceable"],
    "5": ["general", "replaceable"],
    "6": ["special", "replaceable"],
    "7": ["general", "special", "replaceable"],
    "8": ["combination"],
    "9": ["general", "combination"],
    "a": ["special", "combination"],
    "b": ["general", "special", "combination"],
    "c": ["replaceable", "combination"],
    "d": ["general", "replaceable", "combination"],
    "e": ["special", "replaceable", "combination"],
    "f": ["general", "special", "replaceable", "combination"]
}

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return {"error": "Token missing"}, 401

        try:
            decoded = jwt.decode(
                token.split(" ")[1], 
                current_app.config["SECRET_KEY"], 
                algorithms=["HS256"]
            )
            g.user = User.query.get(decoded["id"])
        except:
            return {"error": "Invalid or expired token"}, 401

        return f(*args, **kwargs)
    return decorated

def get_current_day():
    latest_day = db.session.query(func.max(SharePrice.day)).scalar()
    return latest_day or 0

def pay_dividends():
    with current_app.app_context():
        companies = Company.query.all()

        for company in companies:
            ownerships = Ownership.query.filter_by(company_id=company.id).all()
            latest_price = Decimal(get_latest_price(company.id))
            dividend_per_share = latest_price * company.dividends / 100.0

            for own in ownerships:
                user = User.query.get(own.user_id)
                dividend_amount = own.shares_owned * dividend_per_share
                user.balance += dividend_amount

        db.session.commit()
        print("Dividends paid.")

def update_share_prices():
    with current_app.app_context():
        companies = Company.query.all()

        for company in companies:
            latest = (
                SharePrice.query
                .filter_by(company_id=company.id)
                .order_by(SharePrice.day.desc())
                .first()
            )

            if not latest:
                continue

            new_day = latest.day + 1
            last_price = float(latest.price)

            change_factor = 1 + (random.randint(-285, 285) / (100.0 * 1000))
            new_price = round(last_price * change_factor, 2)
            new_entry = SharePrice(
                company_id=company.id,
                day=new_day,
                price=new_price
            )

            db.session.add(new_entry)

        db.session.commit()
        print("Share prices updated.")
        pay_dividends()

def get_latest_two_prices(company_id):
    prices = (
        SharePrice.query
            .filter_by(company_id=company_id)
            .order_by(SharePrice.day.desc())
            .limit(2)
            .all()
    )

    if not prices:
        return (0.0, 0.0)
    if len(prices) == 1:
        return (float(prices[0].price), 0.0)
    return (float(prices[0].price), float(prices[1].price))

def get_user_shares_balance(user_id):
    ownerships = Ownership.query.filter_by(user_id=user_id).all()
    inShares = 0
    for own in ownerships:
        company = Company.query.get(own.company_id)
        latest_price = get_latest_price(company.id)
        inShares += own.shares_owned * latest_price
    
    return inShares

def get_player_holdings(player_id):
    ownerships = Ownership.query.filter_by(user_id=player_id).all()
    result = []

    for own in ownerships:
        company = Company.query.get(own.company_id)
        latest_price_obj = SharePrice.query.filter_by(company_id=company.id).order_by(SharePrice.day.desc()).first()
        latest_price = float(latest_price_obj.price) if latest_price_obj else 0

        result.append({
            "company": company.name,
            "code": company.code,
            "shares_owned": own.shares_owned,
            "current_value": own.shares_owned * latest_price
        })

    return result

def get_company_stocks(company):
    ownerships = Ownership.query.filter_by(company_id=company.id).all()
    sharesData = [{"owner": "Lötinäç'rä Ägavam", "color": "#7E0CE2", "shares": company.gov_shares, "is_user": False}, {"owner": "Insiders", "color": "#FFC800", "shares": company.insider_shares, "is_user": False}]
    IPOShares = 0
    userShares = []
    for own in ownerships:
        userShares.append({
            "owner": own.user.own_company if own.user.own_company else own.user.name,
            "owner_name": own.user.name if own.user.name else None,
            "owner_username": own.user.username if own.user.own_company else None,
            "color": own.user.color if own.user.color else "#{:06x}".format(random.randint(0, 0xFFFFFF)),
            "shares": own.shares_owned,
            "is_user": True
        })
        IPOShares += own.shares_owned
    sharesData.append({"owner": "IPO", "color": "#FFF", "shares": company.float_shares - IPOShares, "is_user": False})
    sharesData.extend(userShares)

    history = SharePrice.query.filter_by(company_id=company.id).order_by(SharePrice.day.desc()).all()
    priceData = []
    for h in history:
        if len(priceData) >= 7:
            break
        
        date = START_DATE + datetime.timedelta(days=h.day)
        priceData.append({
            "day": h.day,
            "date": date.strftime("%d %b"),
            "price": float(h.price)
        })
    
    priceData = list(reversed(priceData))
    return sharesData, priceData

@lru_cache(maxsize=128)
def get_user_info(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": SUPABASE_JWT_SECRET
    }
    response = requests.get(
        f"https://{SUPABASE_PROJECT_ID}.supabase.co/auth/v1/user",
        headers=headers
    )
    if response.status_code == 200:
        return response.json()
    return None

def verify_token(authHeader):
    if not authHeader or not authHeader.startswith("Bearer "):
        return None
    token = authHeader.split(" ")[1]
    return get_user_info(token)

@app.route("/")
def home():
    return jsonify({"message": "Connected to Lutinex API"})

@app.route("/names")
def get_names():
    names = [name for (name,) in db.session.query(Word.word).all()]
    return jsonify(names)

@app.route("/names/morphemes")
def get_morpheme_names():
    names = [name for (name,) in db.session.query(Morpheme.morpheme).all()]
    return jsonify(names)

@app.route("/fetch")
def fetch_words():
    query = request.args.get("q", "").lower()
    filterKey = request.args.get("f", "")

    wordsQuery = Word.query
    if query:
        wordsQuery = wordsQuery.filter(
            or_(
                func.lower(Word.word).like(f"%{query}%"),
                func.cast(Word.meaning, db.Text).ilike(f"%{query}%")
            )
        )

    if filterKey in filterPattern:
        allowedTypes = [t.lower() for t in filterPattern[filterKey]]
        wordsQuery = wordsQuery.filter(func.lower(Word.type).in_(allowedTypes))

    words = wordsQuery.all()

    result = [{
            "id": str(word.id),
            "word": word.word,
            "meaning": word.meaning,
            "type": word.type,
            "phonetic": word.phonetic,
            "combination": word.combination
    } for word in words]

    return jsonify(result)

@app.route("/fetch/morphemes")
def fetch_morphemes():
    query = request.args.get("q", "").lower()

    morphemesQuery = Morpheme.query
    if query:
        morphemesQuery = morphemesQuery.filter(
            or_(
                func.lower(Morpheme.morpheme).like(f"%{query}%"),
                func.cast(Morpheme.meaning, db.Text).ilike(f"%{query}%")
            )
        )

    morphemes = morphemesQuery.all()

    result = [{
            "id": str(morpheme.id),
            "morpheme": morpheme.morpheme,
            "meaning": morpheme.meaning,
            "type": morpheme.type,
            "phonetic": morpheme.phonetic,
            "changes": morpheme.changes
    } for morpheme in morphemes]
    return jsonify(result)

@app.route("/word")
def get_word():
    query = request.args.get("q", "").lower()
    if not query:
        return jsonify([])

    words = Word.query.filter(func.lower(Word.word) == query).all()
    result = [{
        "id": str(word.id),
        "word": word.word,
        "meaning": word.meaning,
        "type": word.type,
        "phonetic": word.phonetic,
        "combination": word.combination
    } for word in words]
    
    return jsonify(result)

@app.route("/word/morpheme")
def get_morpheme():
    query = request.args.get("q", "").lower()
    if not query:
        return jsonify([])

    morphemes = Morpheme.query.filter(func.lower(Morpheme.morpheme) == query).all()
    result = [{
        "id": str(morpheme.id),
        "morpheme": morpheme.morpheme,
        "meaning": morpheme.meaning,
        "type": morpheme.type,
        "phonetic": morpheme.phonetic,
        "changes": morpheme.changes
    } for morpheme in morphemes]

    return jsonify(result)

@app.route("/max")
def get_all_words_count():
    maxCount = db.session.query(func.count(Word.id)).scalar()
    return jsonify({"max": maxCount})

@app.route("/max/morpheme")
def get_all_morphemes_count():
    maxCount = db.session.query(func.count(Morpheme.id)).scalar()
    return jsonify({"max": maxCount})

@app.route("/convert")
def convert_to_script():
    query = request.args.get("q", "").lower()
    characters = list(query)
    charPath = "https://zhyov.github.io/Lutinex/assets/char/"
    consonants = ["p", "b", "f", "v", "w", "k", "g", "t", "d", "đ", "z", "ž", "h", "j", "l", "m", "n", "ň", "r", "s", "š", "c", "č", "ç"]
    vowels = ["a", "ä", "ą", "i", "į", "o", "ö"]
    eshakap = []
    final = []
    i = 0

    while i < len(characters):
        char = characters[i]
        prev = characters[i - 1] if i > 0 else None
        next = characters[i + 1] if i + 1 < len(characters) else None

        if char in vowels and (prev not in consonants):
            final.append({ "id": str(uuid.uuid4()), "path": f"{charPath}aläp.svg" })
            final.append({ "id": str(uuid.uuid4()), "path": f"{charPath}{char}.svg" })
        elif char in consonants and (next is None or next in consonants):
            final.append({ "id": str(uuid.uuid4()), "path": f"{charPath}{char}.svg" })
            final.append({ "id": str(uuid.uuid4()), "path": f"{charPath}∅.svg" })
        elif char in consonants and next in vowels:
            final.append({ "id": str(uuid.uuid4()), "path": f"{charPath}{char}.svg" })
            final.append({ "id": str(uuid.uuid4()), "path": f"{charPath}{next}.svg" })
            i += 1
        else:
            final.append({ "id": str(uuid.uuid4()), "path": f"{charPath}{char}.svg" })

        if len(final) == 2:
            eshakap.append({ "id": str(uuid.uuid4()), "syllable": final })
            final = []

        i += 1
    
    if len(final) > 0:
        eshakap.append({ "id": f"{str(uuid.uuid4())}", "syllable": final })

    return jsonify(eshakap)

@app.route("/order")
def script_order():
    order = ["a", "ä", "ą", "p", "b", "f", "v", "w", "k", "g", "t", "d", "đ", "z", "ž", "i", "į", "h", "j", "l", "m", "n", "ň", "o", "ö", "r", "s", "š", "c", "č", "ç"]

    return jsonify(order)

@app.route("/order/levotin")
def levotin_script_order():
    order = ["α", "β", "γ", "δ", "ε", "η", "ι", "κ", "λ", "μ", "ν", "ο", "π", "ρ", "σ", "ς", "τ", "υ", "φ", "χ", "ω"]

    return jsonify(order)

def get_latest_price(company_id):
    latest = (
        SharePrice.query.filter_by(company_id=company_id)
        .order_by(SharePrice.day.desc())
        .first()
    )
    return float(latest.price) if latest else 0.0

@app.route("/companies")
def get_companies():
    companies = Company.query.all()
    result = []
    for company in companies:
        latest_price, prev_price = get_latest_two_prices(company.id)
        change = latest_price - prev_price
        percent_change = (change / prev_price * 100) if prev_price > 0 else 0

        result.append({
            "id": str(company.id),
            "name": company.name,
            "code": company.code,
            "latest_price": latest_price,
            "previous_price": prev_price,
            "change": change,
            "percent_change": percent_change,
            "total_shares": company.total_shares,
            "dividends": company.dividends
        })
    
    return jsonify(result)

@app.route("/company/<company_id>")
def get_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    latest_price, prev_price = get_latest_two_prices(company.id)
    change = latest_price - prev_price
    percent_change = round((change / prev_price * 100), 2) if prev_price > 0 else 0

    companyInfo = {
        "id": str(company.id),
        "name": company.name,
        "code": company.code,
        "price": latest_price,
        "previous_price": prev_price,
        "change": change,
        "percent_change": percent_change,
        "total_shares": company.total_shares,
        "dividends": company.dividends
    }

    sharesData, priceData = get_company_stocks(company)

    result = {
        "company": companyInfo,
        "price_data": priceData,
        "shares_data": sharesData
    }

    return jsonify(result)

@app.route("/company/<company_id>/history")
def get_company_history(company_id):
    history = SharePrice.query.filter_by(company_id=company_id).order_by(SharePrice.day).all()
    result = [
        {"day": h.day, "price": float(h.price)}
        for h in history
    ]

    return jsonify(result)

@app.route("/user/<player_username>")
def get_user_by_username(player_username):
    user = User.query.filter(User.username == player_username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    result = {
        "id": str(user.id),
        "username": user.username,
        "name": user.name,
        "color": user.color,
        "own_company": user.own_company,
        "balance": float(user.balance),
        "in_shares": get_user_shares_balance(user.id),
        "stocks": get_player_holdings(user.id)
    }

    return jsonify(result)

@app.route("/users")
def get_users():
    users = User.query.all()
    result = []
    for user in users:
        result.append({
            "id": str(user.id),
            "username": user.username,
            "name": user.name,
            "color": user.color,
            "own_company": user.own_company,
            "balance": float(user.balance),
            "in_shares": get_user_shares_balance(user.id)
        })

    return jsonify(result)

@app.route("/stocks")
def get_stocks():
    companies = Company.query.all()
    result = []

    for company in companies:
        latest_price, prev_price = get_latest_two_prices(company.id)
        change = latest_price - prev_price
        percent_change = (change / prev_price * 100) if prev_price > 0 else 0

        companyInfo = {
            "id": str(company.id),
            "name": company.name,
            "code": company.code,
            "price": latest_price,
            "previous_price": prev_price,
            "change": change,
            "percent_change": percent_change,
            "total_shares": company.total_shares
        }

        sharesData, priceData = get_company_stocks(company)

        result.append({
            "company": companyInfo,
            "shares_data": sharesData,
            "price_data": priceData
        })

    return jsonify(result)

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return {"error": "No JSON data provided"}, 400

    if User.query.filter_by(username=data["username"]).first():
        return {"error": "Username already taken"}, 400
    
    if not data["name"]:
        data["name"] = data["username"]

    user = User(
        name=data["name"],
        username=data["username"],
        color=data.get("color", "#{:06x}".format(random.randint(0, 0xFFFFFF))),
        own_company=None,
        balance=0
    )
    
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    return {"message": "User registered successfully"}, 201

@app.route("/auth/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(username=data["username"]).first()

    if not user:
        return {"error": "Invalid username"}, 401
    
    if not user.check_password(data["password"]):
        return {"error": "Invalid password"}, 401

    token = create_access_token(identity=str(user.id), expires_delta=datetime.timedelta(hours=24))

    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "name": user.name,
            "color": user.color,
            "balance": float(user.balance),
            "own_company": user.own_company
        }
    }

@app.route("/stock-update", methods=["POST"])
def trigger_update_prices():
    auth = request.headers.get("X-CRON-KEY")
    if auth != os.environ.get("CRON_SECRET"):
        return {"error": "Unauthorized"}, 403
    
    update_share_prices()
    return {"message": "Share prices updated successfully"}

@app.route("/stocks/buy", methods=["POST"])
@jwt_required()
def buy_shares():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return {"error": "User not found"}, 404

    data = request.json
    company_id = data.get("company_id")
    shares_to_buy = int(data.get("shares", 0))

    if shares_to_buy <= 0:
        return {"error": "Invalid number of shares"}, 400

    company = Company.query.get(company_id)
    if not company:
        return {"error": "Company not found"}, 404

    latest_price = get_latest_price(company.id)
    total_cost = latest_price * shares_to_buy

    if user.balance < total_cost:
        return {"error": "Insufficient balance"}, 400

    user.balance -= Decimal(total_cost)

    ownership = Ownership.query.filter_by(user_id=user.id, company_id=company.id).first()
    if ownership:
        ownership.shares_owned += shares_to_buy
    else:
        ownership = Ownership(
            company_id=company.id,
            user_id=user.id,
            day=get_current_day(),
            shares_owned=shares_to_buy
        )
        db.session.add(ownership)

    db.session.commit()
    return {"message": f"Bought {shares_to_buy} shares of {company.name}", "balance": float(user.balance)}

@app.route("/stocks/sell", methods=["POST"])
@jwt_required()
def sell_shares():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return {"error": "User not found"}, 404

    data = request.json
    company_id = data.get("company_id")
    shares_to_sell = int(data.get("shares", 0))

    if shares_to_sell <= 0:
        return {"error": "Invalid number of shares"}, 400

    company = Company.query.get(company_id)
    if not company:
        return {"error": "Company not found"}, 404

    ownership = Ownership.query.filter_by(user_id=user.id, company_id=company.id).first()
    if not ownership or ownership.shares_owned < shares_to_sell:
        return {"error": "Not enough shares to sell"}, 400

    latest_price = get_latest_price(company.id)
    total_value = latest_price * shares_to_sell

    user.balance += Decimal(total_value)
    ownership.shares_owned -= Decimal(shares_to_sell)

    if ownership.shares_owned == 0:
        db.session.delete(ownership)

    db.session.commit()
    return {"message": f"Sold {shares_to_sell} shares of {company.name}", "balance": float(user.balance)}

@app.route("/auth/update", methods=["PATCH"])
@jwt_required()
def update_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return {"error": "User not found"}, 404

    data = request.json

    if "name" in data:
        user.name = data["name"]
    if "color" in data:
        user.color = data["color"]
    if "own_company" in data:
        user.own_company = data["own_company"]

    db.session.commit()

    return {
        "message": "User updated successfully",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "name": user.name,
            "color": user.color,
            "own_company": user.own_company,
            "balance": float(user.balance)
        }
    }

if __name__ == "__main__":
    if os.environ.get("FLASK_ENV") == "development":
        with app.app_context():
            db.create_all()
    app.run()
