from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import httpx, os

app = FastAPI(
    title="MilaMart Labs API",
    description="Search and browse MilaMart Labs — a curated product store powered by real product data and images.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DUMMYJSON_URL = "https://dummyjson.com/products?limit=194"

# Categories to exclude
EXCLUDED_CATEGORIES = {"groceries", "kitchen-accessories"}

# Brands to assign to home-decoration products (DummyJSON has none)
HOME_DECO_BRANDS = [
    "IKEA", "West Elm", "HAY", "Muuto", "Ferm Living",
    "Menu", "&Tradition", "Normann Copenhagen", "Hay", "Vitra",
]

# Cache so we don't fetch on every request
_cache = None

async def get_products():
    global _cache
    if _cache is not None:
        return _cache
    async with httpx.AsyncClient() as client:
        r = await client.get(DUMMYJSON_URL, timeout=10)
        data = r.json()
    products = []
    home_deco_idx = 0
    for p in data["products"]:
        # Skip excluded categories
        if p["category"] in EXCLUDED_CATEGORIES:
            continue
        # Assign brand to home-decoration if missing
        brand = p.get("brand") or ""
        if p["category"] == "home-decoration" and not brand:
            brand = HOME_DECO_BRANDS[home_deco_idx % len(HOME_DECO_BRANDS)]
            home_deco_idx += 1
        products.append({
            "id":          str(p["id"]),
            "name":        p["title"],
            "brand":       brand,
            "category":    p["category"].replace("-", " ").title(),
            "price":       p["price"],
            "description": p["description"],
            "rating":      p["rating"],
            "stock":       p["stock"],
            "image":       p["thumbnail"],
        })
    _cache = products
    return products

def filter_products(products, query="", category=""):
    results = products
    if query:
        q = query.lower()
        results = [p for p in results if
                   q in p["name"].lower() or
                   q in p["description"].lower() or
                   q in p["category"].lower() or
                   q in p.get("brand", "").lower()]
    if category:
        results = [p for p in results if p["category"].lower() == category.lower()]
    return results

# ─── FRONTEND ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def homepage():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MilaMart Labs</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&family=DM+Serif+Display:ital@0;1&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:      #faf9f7;
    --white:   #ffffff;
    --border:  #ede9e3;
    --text:    #2c2825;
    --muted:   #9c9690;
    --soft:    #f3f0eb;
    --accent:  #5c7a6a;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; font-weight:300; }

  header {
    background:var(--white); border-bottom:1px solid var(--border);
    padding:0 48px; height:60px; display:flex; align-items:center;
    justify-content:space-between; position:sticky; top:0; z-index:100;
  }
  .logo { font-family:'DM Serif Display',serif; font-size:1.25rem; color:var(--text); }
  .logo em { font-style:italic; color:var(--accent); }
  .header-right { font-size:.78rem; color:var(--muted); font-weight:300; }

  .hero { padding:72px 48px 40px; max-width:680px; }
  .hero-label { font-size:.7rem; letter-spacing:2.5px; text-transform:uppercase; color:var(--muted); margin-bottom:20px; }
  .hero h1 { font-family:'DM Serif Display',serif; font-size:clamp(2rem,4vw,3rem); font-weight:400; line-height:1.15; margin-bottom:28px; }
  .hero h1 em { font-style:italic; color:var(--accent); }

  .search-wrap {
    display:flex; max-width:500px;
    border:1px solid var(--border); border-radius:6px;
    background:var(--white); overflow:hidden; transition:border-color .2s;
  }
  .search-wrap:focus-within { border-color:var(--accent); }
  .search-wrap input {
    flex:1; padding:12px 18px; border:none; outline:none;
    font-family:'DM Sans',sans-serif; font-weight:300; font-size:.9rem;
    color:var(--text); background:transparent;
  }
  .search-wrap input::placeholder { color:var(--muted); }
  .search-wrap button {
    padding:12px 22px; background:var(--text); color:var(--white);
    border:none; font-family:'DM Sans',sans-serif; font-weight:400;
    font-size:.82rem; cursor:pointer; transition:background .2s;
  }
  .search-wrap button:hover { background:var(--accent); }

  .cat-strip { padding:24px 48px 16px; display:flex; gap:8px; flex-wrap:wrap; }
  .cat-btn {
    padding:6px 16px; border-radius:100px; border:1px solid var(--border);
    background:var(--white); font-family:'DM Sans',sans-serif; font-weight:300;
    font-size:.82rem; color:var(--muted); cursor:pointer; transition:all .18s;
  }
  .cat-btn:hover { border-color:var(--text); color:var(--text); }
  .cat-btn.active { background:var(--text); border-color:var(--text); color:var(--white); font-weight:400; }

  .toolbar { padding:0 48px 16px; display:flex; align-items:center; gap:16px; }
  .toolbar-line { flex:1; height:1px; background:var(--border); }
  .toolbar-count { font-size:.75rem; color:var(--muted); font-weight:300; white-space:nowrap; }

  .grid {
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
    gap:1px; background:var(--border); border-top:1px solid var(--border);
  }
  .card {
    background:var(--white); overflow:hidden;
    transition:background .18s; cursor:pointer;
    animation:fadeIn .3s ease both;
  }
  .card:hover { background:var(--soft); }
  @keyframes fadeIn { from{opacity:0} to{opacity:1} }
  .card-img { width:100%; height:200px; object-fit:cover; display:block; background:#f0ede8; }
  .card-body { padding:16px 18px 18px; }
  .card-cat {
    display:inline-block; font-size:.65rem; font-weight:400;
    letter-spacing:1px; text-transform:uppercase;
    padding:3px 9px; border-radius:100px;
    background:var(--soft); color:var(--muted); margin-bottom:8px;
  }
  .card-brand { font-size:.68rem; color:var(--muted); font-weight:400; letter-spacing:.5px; text-transform:uppercase; margin-bottom:3px; }
  .card-name { font-family:'DM Serif Display',serif; font-size:.97rem; font-weight:400; line-height:1.35; margin-bottom:6px; }
  .card-desc { font-size:.77rem; color:var(--muted); line-height:1.6; margin-bottom:14px; font-weight:300;
    display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
  .card-foot { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
  .card-price { font-size:.95rem; font-weight:400; }
  .card-rating { font-size:.72rem; color:var(--muted); font-weight:300; }
  .card-rating span { color:#c8a96e; }
  .card-btn {
    width:100%; padding:9px; background:transparent;
    border:1px solid var(--border); border-radius:4px;
    color:var(--text); font-family:'DM Sans',sans-serif;
    font-weight:300; font-size:.8rem; cursor:pointer; transition:all .18s;
  }
  .card-btn:hover { background:var(--text); color:var(--white); border-color:var(--text); }

  .loading { grid-column:1/-1; text-align:center; padding:80px; color:var(--muted); font-size:.9rem; }
  .empty-wrap { background:var(--white); grid-column:1/-1; text-align:center; padding:100px; }
  .empty-wrap h3 { font-family:'DM Serif Display',serif; font-size:1.3rem; margin-bottom:8px; }
  .empty-wrap p { font-size:.85rem; color:var(--muted); }

  footer {
    border-top:1px solid var(--border); padding:28px 48px;
    display:flex; align-items:center; justify-content:space-between;
    font-size:.75rem; color:var(--muted);
  }
  footer a { color:var(--muted); text-decoration:none; margin-left:20px; }
  footer a:hover { color:var(--text); }

  @media(max-width:640px) {
    header,footer,.hero,.cat-strip,.toolbar { padding-left:20px; padding-right:20px; }
    .grid { grid-template-columns:repeat(2,1fr); }
    .hero h1 { font-size:1.7rem; }
  }
</style>
</head>
<body>

<header>
  <div class="logo">Mila<em>Mart</em> Labs</div>
  <div class="header-right" id="headerCount">Loading...</div>
</header>

<div class="hero">
  <div class="hero-label">Curated Store &middot; AI Discoverable</div>
  <h1>Simple shopping,<br><em>beautifully</em> organised.</h1>
  <div class="search-wrap">
    <input type="text" id="searchInput" placeholder="Search products, brands..." autocomplete="off">
    <button onclick="doSearch()">Search</button>
  </div>
</div>

<div class="cat-strip" id="catStrip">
  <button class="cat-btn active" onclick="filterCat('',this)">All</button>
</div>

<div class="toolbar">
  <div class="toolbar-line"></div>
  <div class="toolbar-count" id="barCount">Loading...</div>
  <div class="toolbar-line"></div>
</div>

<div class="grid" id="grid">
  <div class="loading">Loading real products...</div>
</div>

<footer>
  <span>MilaMart Labs &mdash; POC Demo</span>
  <span>
    <a href="/docs">API Docs</a>
    <a href="/llms.txt">llms.txt</a>
    <a href="/openapi.json">OpenAPI</a>
  </span>
</footer>

<script>
  let allProducts = [];
  let currentCat = '', currentQ = '';

  async function init() {
    // Load products from our own backend (which fetches from DummyJSON)
    const r = await fetch('/api/products?limit=200');
    const data = await r.json();
    allProducts = data.products;

    // Build category buttons dynamically
    const cats = [...new Set(allProducts.map(p => p.category))].sort();
    const strip = document.getElementById('catStrip');
    cats.forEach(cat => {
      const btn = document.createElement('button');
      btn.className = 'cat-btn';
      btn.textContent = cat;
      btn.onclick = () => filterCat(cat, btn);
      strip.appendChild(btn);
    });

    document.getElementById('headerCount').textContent = allProducts.length + ' products';
    render(allProducts);
  }

  function applyFilters() {
    let results = allProducts;
    if (currentQ) {
      const q = currentQ.toLowerCase();
      results = results.filter(p =>
        p.name.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q) ||
        (p.brand || '').toLowerCase().includes(q)
      );
    }
    if (currentCat) {
      results = results.filter(p => p.category.toLowerCase() === currentCat.toLowerCase());
    }
    return results;
  }

  function render(products) {
    const grid  = document.getElementById('grid');
    const count = document.getElementById('barCount');
    const label = currentQ ? ` for "${currentQ}"` : '';
    const cat   = currentCat ? ` in ${currentCat}` : '';
    count.textContent = `${products.length} product${products.length !== 1 ? 's' : ''}${label}${cat}`;

    if (!products.length) {
      grid.innerHTML = '<div class="empty-wrap"><h3>Nothing found</h3><p>Try a different keyword or category.</p></div>';
      return;
    }

    grid.innerHTML = products.map((p, i) => `
      <div class="card" style="animation-delay:${Math.min(i,24)*0.02}s">
        <img class="card-img" src="${p.image}" alt="${p.name}" loading="lazy">
        <div class="card-body">
          <span class="card-cat">${p.category}</span>
          <div class="card-brand">${p.brand || ''}</div>
          <div class="card-name">${p.name}</div>
          <div class="card-desc">${p.description}</div>
          <div class="card-foot">
            <div class="card-price">$${p.price.toFixed(2)}</div>
            <div class="card-rating"><span>&#9733;</span> ${p.rating} &middot; ${p.stock} left</div>
          </div>
          <button class="card-btn">Add to cart</button>
        </div>
      </div>`).join('');
  }

  function doSearch() {
    currentQ = document.getElementById('searchInput').value.trim();
    render(applyFilters());
  }

  function filterCat(cat, el) {
    currentCat = cat;
    document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
    render(applyFilters());
  }

  document.getElementById('searchInput')
    .addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

  init();
</script>
</body>
</html>"""

# ─── API ENDPOINTS ─────────────────────────────────────────────────────────────
@app.get("/api/products", summary="Get all products")
async def get_all_products(limit: int = Query(100)):
    """Returns the full MilaMart Labs product catalog."""
    products = await get_products()
    return {"total": len(products), "products": products[:limit]}

@app.get("/api/products/search", summary="Search products by keyword and/or category")
async def search_products(
    query: Optional[str] = Query(None, description="Keyword e.g. phone, laptop, skincare"),
    category: Optional[str] = Query(None, description="Category to filter by"),
    max_results: int = Query(20, description="Max results to return")
):
    """Search MilaMart Labs products. Use when a user wants to find or browse products."""
    products = await get_products()
    results = filter_products(products, query or "", category or "")[:max_results]
    return {"query": query, "category": category, "total": len(results), "products": results}

@app.get("/api/products/{product_id}", summary="Get a single product by ID")
async def get_product(product_id: str):
    """Get full details of a specific product by ID."""
    products = await get_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return JSONResponse(status_code=404, content={"error": "Product not found"})
    return product

@app.get("/api/categories", summary="List all product categories")
async def get_categories():
    """Returns all available product categories."""
    products = await get_products()
    cats = sorted(set(p["category"] for p in products))
    return {"categories": cats}

# ─── AI DISCOVERABILITY ───────────────────────────────────────────────────────
@app.get("/llms.txt", response_class=PlainTextResponse, include_in_schema=False)
async def llms_txt():
    products = await get_products()
    count = len(products)
    cats = sorted(set(p["category"] for p in products))
    cat_list = ", ".join(cats)
    return f"""# MilaMart Labs — AI-Discoverable Product Store

> MilaMart Labs is a curated store with {count} real products and real images.
> Categories: {cat_list}.
> Use this to help users search and browse products by keyword or category.

## Product API
- [Search Products](/api/products/search?query=phone): Search by keyword
- [Browse by Category](/api/products/search?category=smartphones): Filter by category
- [All Products](/api/products): Full catalog
- [Single Product](/api/products/1): Get product by ID
- [Categories](/api/categories): List all categories

## Example Searches
- /api/products/search?query=laptop
- /api/products/search?query=skincare
- /api/products/search?category=smartphones

## API Docs
- [Interactive Docs](/docs): Full Swagger UI
- [OpenAPI Spec](/openapi.json): Machine-readable spec
"""

@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt():
    return """User-agent: *
Allow: /
User-agent: GPTBot
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Google-Extended
Allow: /
"""

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def ai_plugin():
    return {
        "schema_version": "v1",
        "name_for_human": "MilaMart Labs",
        "name_for_model": "milamart_labs",
        "description_for_model": "Search MilaMart Labs product catalog by keyword or category. Returns product name, brand, price, description, rating and stock.",
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": "/openapi.json"},
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)