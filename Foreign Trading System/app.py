import os, sqlite3, time, requests
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","replace-this-secret-key")
DB=os.path.join(os.path.dirname(__file__),"trading.db")
# Product prices are stored in the product's local currency, not INR.
# The app converts them using the latest available Frankfurter reference rate.
SAMPLE=[
("Japan","Wireless Earbuds","Electronics","Bluetooth audio earbuds with charging case",4200,"JPY","audio bluetooth wireless"),
("Japan","Digital Camera","Electronics","Compact camera for travel photography",32000,"JPY","camera photography travel"),
("South Korea","Smart Watch","Electronics","Fitness tracking smartwatch",85000,"KRW","watch fitness wearable"),
("Germany","Mechanical Keyboard","Electronics","Mechanical computer keyboard for gaming",85,"EUR","keyboard computer gaming"),
("Italy","Leather Wallet","Fashion","Leather wallet with card slots",45,"EUR","wallet leather fashion"),
("France","Skincare Set","Beauty","Daily skincare and face care products",55,"EUR","skincare beauty face care"),
("United Kingdom","Travel Backpack","Accessories","Durable backpack for travel",48,"GBP","backpack travel bag"),
("United States","Running Shoes","Fashion","Lightweight running shoes for exercise",75,"USD","shoes running sports"),
("China","Desk Lamp","Home","LED desk lamp with adjustable brightness",180,"CNY","lamp led lighting"),
("Switzerland","Wrist Watch","Fashion","Minimal stainless steel wrist watch",120,"CHF","watch fashion accessory")]
# Additional international catalogue products (local-currency prices).
MORE_PRODUCTS=[
("Japan","Gaming Mouse","Electronics","Ergonomic wireless gaming mouse",6500,"JPY","mouse gaming computer wireless"),
("Japan","Portable Bluetooth Speaker","Electronics","Compact waterproof portable speaker",7800,"JPY","speaker bluetooth audio music"),
("Japan","Instant Film Camera","Electronics","Instant photo camera for travel and memories",12500,"JPY","camera photography instant"),
("Japan","Ceramic Tea Set","Home","Traditional ceramic tea cup and pot set",5200,"JPY","tea ceramic kitchen home"),
("South Korea","Wireless Headphones","Electronics","Over-ear noise isolating wireless headphones",99000,"KRW","headphones audio wireless music"),
("South Korea","LED Skincare Mask","Beauty","LED facial care mask for home use",145000,"KRW","beauty skincare face led"),
("South Korea","Compact Air Purifier","Home","Small room air purifier with replaceable filter",110000,"KRW","air purifier home appliance"),
("Germany","Noise Cancelling Headphones","Electronics","Over-ear headphones with active noise cancellation",149,"EUR","headphones audio noise cancelling"),
("Germany","Coffee Grinder","Home","Burr coffee grinder with adjustable settings",79,"EUR","coffee grinder kitchen appliance"),
("Germany","Smart Home Plug","Electronics","Wi-Fi smart plug with energy monitoring",24,"EUR","smart home plug wifi"),
("Germany","Travel Suitcase","Accessories","Hard-shell cabin suitcase with spinner wheels",119,"EUR","suitcase travel luggage"),
("Italy","Leather Handbag","Fashion","Classic Italian leather everyday handbag",135,"EUR","handbag leather fashion"),
("Italy","Sunglasses","Fashion","UV-protection fashion sunglasses",68,"EUR","sunglasses eyewear fashion"),
("Italy","Espresso Maker","Home","Stovetop espresso coffee maker",39,"EUR","coffee espresso kitchen"),
("France","Perfume Gift Set","Beauty","Fragrance gift set for daily use",89,"EUR","perfume fragrance beauty"),
("France","Luxury Face Moisturizer","Beauty","Hydrating daily face moisturizer",42,"EUR","skincare moisturizer beauty"),
("France","Designer Scarf","Fashion","Soft patterned scarf for everyday styling",58,"EUR","scarf fashion accessory"),
("United Kingdom","Mechanical Pencil Set","Stationery","Precision mechanical pencils and accessories",18,"GBP","stationery pencil office"),
("United Kingdom","Fitness Tracker","Electronics","Activity tracker with sleep and step monitoring",64,"GBP","fitness tracker wearable watch"),
("United Kingdom","Insulated Water Bottle","Accessories","Reusable insulated stainless steel bottle",22,"GBP","bottle drink travel"),
("United States","Smart Fitness Watch","Electronics","Smartwatch with heart-rate and activity tracking",129,"USD","watch fitness wearable"),
("United States","Portable SSD 1TB","Electronics","Compact external solid state storage drive",99,"USD","ssd storage computer"),
("United States","Wireless Charging Pad","Electronics","Fast wireless charging pad for compatible phones",29,"USD","charger wireless phone"),
("United States","Running Jacket","Fashion","Lightweight weather-resistant running jacket",85,"USD","jacket running sports clothing"),
("China","Mini Projector","Electronics","Portable LED projector for home entertainment",520,"CNY","projector home cinema electronics"),
("China","Mechanical Keyboard Kit","Electronics","Customizable mechanical keyboard kit",360,"CNY","keyboard computer gaming"),
("China","Robot Vacuum Cleaner","Home","Automatic vacuum cleaner for home floors",899,"CNY","vacuum robot home appliance"),
("China","Phone Gimbal Stabilizer","Electronics","Handheld stabilizer for smooth mobile videos",430,"CNY","camera phone video gimbal"),
("Switzerland","Premium Fountain Pen","Stationery","Precision metal fountain pen",95,"CHF","pen writing stationery"),
("Switzerland","Travel Alarm Clock","Accessories","Compact travel clock with alarm",38,"CHF","clock travel accessories"),
("Switzerland","Outdoor Backpack","Accessories","Durable daypack for hiking and travel",110,"CHF","backpack outdoor hiking travel"),
("Australia","Merino Wool Sweater","Fashion","Soft merino wool sweater for cool weather",115,"AUD","sweater wool fashion clothing"),
("Australia","Reusable Coffee Cup","Home","Insulated reusable cup for hot drinks",32,"AUD","coffee cup reusable kitchen"),
("Canada","Winter Gloves","Fashion","Warm insulated gloves for winter",48,"CAD","gloves winter clothing"),
("Canada","Camping Lantern","Outdoor","Rechargeable LED lantern for camping",56,"CAD","lantern camping outdoor lighting"),
("Singapore","Compact Travel Adapter","Electronics","Universal travel adapter with USB ports",35,"SGD","adapter travel charger electronics"),
("Singapore","Desk Organizer","Home","Minimal desktop organizer for office supplies",28,"SGD","desk organizer office home"),
("Sweden","Minimal Table Lamp","Home","Scandinavian-style LED table lamp",72,"EUR","lamp lighting home decor"),
("Netherlands","Bicycle Phone Mount","Accessories","Adjustable phone holder for bicycle handlebars",24,"EUR","bike bicycle phone mount"),
("Spain","Leather Card Holder","Fashion","Slim genuine leather card holder",29,"EUR","wallet leather card holder"),
("Turkey","Decorative Ceramic Vase","Home","Handcrafted decorative ceramic vase",850,"TRY","vase ceramic home decor")
]

# Small in-process cache prevents an API request for every product card.
RATE_CACHE = {}
RATE_CACHE_SECONDS = 3600
FRANKFURTER_API = "https://api.frankfurter.dev/v2/rate"


def db():
    if "db" not in g:
        g.db=sqlite3.connect(DB); g.db.row_factory=sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    con=g.pop("db",None)
    if con: con.close()

def init_db():
    con=sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,password_hash TEXT,role TEXT DEFAULT 'buyer');
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,country TEXT,name TEXT,category TEXT,description TEXT,price_inr REAL,tags TEXT);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,user_id INTEGER,product_id INTEGER,quantity INTEGER,total_inr REAL,status TEXT,fraud_score INTEGER DEFAULT 0,fraud_reasons TEXT DEFAULT '',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    """)
    # Backward-compatible migrations for an existing project database.
    pcols={r[1] for r in con.execute("PRAGMA table_info(products)")}
    if "currency_code" not in pcols: con.execute("ALTER TABLE products ADD COLUMN currency_code TEXT DEFAULT 'INR'")
    if "original_price" not in pcols: con.execute("ALTER TABLE products ADD COLUMN original_price REAL")
    # Existing rows remain INR so their old sample values are not misinterpreted.
    con.execute("UPDATE products SET original_price=price_inr WHERE original_price IS NULL")
    ocols={r[1] for r in con.execute("PRAGMA table_info(orders)")}
    if "fraud_score" not in ocols: con.execute("ALTER TABLE orders ADD COLUMN fraud_score INTEGER DEFAULT 0")
    if "fraud_reasons" not in ocols: con.execute("ALTER TABLE orders ADD COLUMN fraud_reasons TEXT DEFAULT ''")
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0]==0:
        con.executemany("INSERT INTO products(country,name,category,description,price_inr,tags,currency_code,original_price) VALUES(?,?,?,?,?,?,?,?)",
                        [(country,name,cat,desc,price," ".join(tags.split()),currency,price) for country,name,cat,desc,price,currency,tags in SAMPLE])
    # Add the expanded catalogue safely without duplicating products on each restart.
    existing={r[0] for r in con.execute("SELECT name FROM products")}
    additions=[(country,name,cat,desc,price,tags,currency,price) for country,name,cat,desc,price,currency,tags in MORE_PRODUCTS if name not in existing]
    if additions:
        con.executemany("INSERT INTO products(country,name,category,description,price_inr,tags,currency_code,original_price) VALUES(?,?,?,?,?,?,?,?)", additions)
    con.commit(); con.close()

def get_exchange_rate(currency):
    """Return INR per one unit of currency and the API's effective date."""
    currency=(currency or "INR").upper()
    if currency == "INR":
        return Decimal("1"), "INR"
    now=time.time()
    cached=RATE_CACHE.get(currency)
    if cached and now-cached[0] < RATE_CACHE_SECONDS:
        return cached[1], cached[2]
    response=requests.get(f"{FRANKFURTER_API}/{currency}/INR", timeout=8)
    response.raise_for_status()
    payload=response.json()
    rate=Decimal(str(payload["rate"]))
    rate_date=payload.get("date", "Latest available rate")
    RATE_CACHE[currency]=(now,rate,rate_date)
    return rate,rate_date

def price_in_inr(product):
    """Calculate a product's display/checkout price in INR."""
    currency=product["currency_code"] or "INR"
    original=Decimal(str(product["original_price"] if product["original_price"] is not None else product["price_inr"]))
    rate,rate_date=get_exchange_rate(currency)
    total=(original*rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result=dict(product)
    result.update({"converted_price_inr": float(total), "exchange_rate": str(rate), "rate_date": rate_date})
    return result

def login_required(fn):
    @wraps(fn)
    def wrap(*a,**kw):
        if not session.get("uid"):
            flash("Please log in first.","warning"); return redirect(url_for("login"))
        return fn(*a,**kw)
    return wrap

def recommend(pid,limit=4):
    products=db().execute("SELECT * FROM products").fetchall()
    if len(products)<2:return []
    texts=[f"{p['name']} {p['category']} {p['description']} {p['tags']}" for p in products]
    matrix=TfidfVectorizer(stop_words="english").fit_transform(texts)
    sims=cosine_similarity(matrix,matrix)
    idx={p["id"]:i for i,p in enumerate(products)}.get(pid)
    if idx is None:return []
    ranked=sorted([(i,float(sims[idx][i])) for i in range(len(products)) if i!=idx],key=lambda x:x[1],reverse=True)
    return [dict(products[i],similarity=s) for i,s in ranked[:limit] if s>0]

def fraud_check(uid,qty,total):
    # Educational, explainable rules; NOT a trained ML fraud model.
    score=0; reasons=[]
    if total>=50000: score+=40; reasons.append("High transaction value (₹50,000+)")
    if qty>=6: score+=25; reasons.append("High quantity (6+ units)")
    if qty>=10: score+=15; reasons.append("Very high quantity (10+ units)")
    recent=db().execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND datetime(created_at)>=datetime('now','-10 minutes')",(uid,)).fetchone()[0]
    if recent>=3: score+=30; reasons.append("Multiple recent orders in 10 minutes")
    score=min(score,100)
    status="Pending manual review" if score>=50 else "Order placed"
    return score,reasons,status

@app.route("/")
def home():
    q=request.args.get("q","").strip(); cat=request.args.get("category","").strip()
    sql="SELECT * FROM products WHERE 1=1"; args=[]
    if q:
        sql+=" AND (name LIKE ? OR country LIKE ? OR description LIKE ? OR tags LIKE ?)"
        args += [f"%{q}%"]*4
    if cat: sql+=" AND category=?"; args.append(cat)
    products=db().execute(sql+" ORDER BY name",args).fetchall()
    try:
        products=[price_in_inr(p) for p in products]
        rate_error=None
    except (requests.RequestException, KeyError, ValueError, TypeError):
        products=[]
        rate_error="Exchange rates are temporarily unavailable. Please refresh in a moment."
    cats=[r[0] for r in db().execute("SELECT DISTINCT category FROM products ORDER BY category")]
    return render_template("home.html",products=products,categories=cats,q=q,cat=cat,rate_error=rate_error)

@app.route("/suggest")
def suggest():
    q=request.args.get("q", "").strip()
    if len(q)<1:
        return jsonify([])
    rows=db().execute("""SELECT id,name,country,category FROM products
        WHERE name LIKE ? OR country LIKE ? OR category LIKE ? OR description LIKE ? OR tags LIKE ?
        ORDER BY CASE WHEN name LIKE ? THEN 0 ELSE 1 END, name LIMIT 8""",
        (f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%",f"{q}%")).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/product/<int:pid>")
def product(pid):
    p=db().execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
    if not p: flash("Product not found.","danger"); return redirect(url_for("home"))
    try:
        p=price_in_inr(p)
        recommendations=[price_in_inr(r) for r in recommend(pid)]
        rate_error=None
    except (requests.RequestException, KeyError, ValueError, TypeError):
        flash("Exchange rate service is unavailable. Prices and checkout are temporarily disabled.","danger")
        p=dict(p); p["converted_price_inr"]=None; p["rate_date"]="Unavailable"
        recommendations=[]; rate_error="Exchange rates unavailable"
    return render_template("product.html",p=p,recommendations=recommendations,rate_error=rate_error)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
        if not name or not email or len(pw)<8: flash("Enter details; password must be at least 8 characters.","danger")
        else:
            try:
                db().execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",(name,email,generate_password_hash(pw))); db().commit()
                flash("Account created. Please log in.","success"); return redirect(url_for("login"))
            except sqlite3.IntegrityError: flash("Email already registered.","danger")
    return render_template("auth.html",mode="Register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=db().execute("SELECT * FROM users WHERE email=?",(request.form.get("email","").strip().lower(),)).fetchone()
        if u and check_password_hash(u["password_hash"],request.form.get("password","")):
            session.clear(); session["uid"]=u["id"]; session["name"]=u["name"]; session["role"]=u["role"]
            return redirect(url_for("home"))
        flash("Invalid email or password.","danger")
    return render_template("auth.html",mode="Login")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.route("/buy/<int:pid>",methods=["POST"])
@login_required
def buy(pid):
    p=db().execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
    if not p: flash("Product not found.","danger"); return redirect(url_for("home"))
    try: qty=int(request.form.get("quantity",1))
    except ValueError: qty=1
    qty=max(1,min(qty,20))
    try:
        converted=price_in_inr(p)
    except (requests.RequestException, KeyError, ValueError, TypeError):
        flash("Could not fetch the latest exchange rate. No order was created; please try again.","danger")
        return redirect(url_for("product",pid=pid))
    total=round(converted["converted_price_inr"]*qty,2)
    score,reasons,status=fraud_check(session["uid"],qty,total)
    reason="; ".join(reasons) if reasons else "No demo risk rules triggered"
    cur=db().execute("INSERT INTO orders(user_id,product_id,quantity,total_inr,status,fraud_score,fraud_reasons) VALUES(?,?,?,?,?,?,?)",
                     (session["uid"],pid,qty,total,status,score,reason))
    db().commit()
    flash(f"Order #{cur.lastrowid}: {status}. Risk score {score}/100. No real payment was taken.","warning" if score>=50 else "success")
    return redirect(url_for("orders"))

@app.route("/orders")
@login_required
def orders():
    rows=db().execute("""SELECT o.*,p.name product_name FROM orders o JOIN products p ON p.id=o.product_id WHERE o.user_id=? ORDER BY o.created_at DESC""",(session["uid"],)).fetchall()
    return render_template("orders.html",orders=rows)

@app.route("/admin")
@login_required
def admin():
    if session.get("role")!="admin": flash("Admin only.","danger"); return redirect(url_for("home"))
    flagged=db().execute("""SELECT o.*,u.name buyer,p.name product_name FROM orders o JOIN users u ON u.id=o.user_id JOIN products p ON p.id=o.product_id WHERE o.status='Pending manual review'""").fetchall()
    return render_template("admin.html",flagged=flagged)

@app.route("/admin/review/<int:oid>",methods=["POST"])
@login_required
def review(oid):
    if session.get("role")!="admin": return redirect(url_for("home"))
    status="Approved after review" if request.form.get("decision")=="approve" else "Rejected after review"
    db().execute("UPDATE orders SET status=? WHERE id=? AND status='Pending manual review'",(status,oid)); db().commit()
    return redirect(url_for("admin"))

if __name__=="__main__":
    init_db()
    app.run(debug=True)
