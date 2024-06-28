import os
from flask import Flask, render_template, request, jsonify
import requests
import json
from bs4 import BeautifulSoup

app = Flask(__name__)

# Fungsi untuk menyimpan token ke environment variable
def save_token(token):
    os.environ['TOKEN_JSON'] = json.dumps(token)

# Fungsi untuk memuat token dari environment variable
def load_token():
    token_json = os.getenv('TOKEN_JSON')
    if token_json:
        return json.loads(token_json)
    else:
        return None

# Fungsi untuk memperbarui token menggunakan refresh_token
def refresh_access_token():
    token = load_token()
    url = 'https://oauth2.googleapis.com/token'
    data = {
        'client_id': '811953646580-ivufat7803bcc3cbh0hmqskpg0e9abkl.apps.googleusercontent.com',
        'client_secret': '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',
        'refresh_token': token['refresh_token'],
        'grant_type': 'refresh_token'
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        new_token = response.json()
        token['access_token'] = new_token['access_token']
        token['expires_in'] = new_token['expires_in']
        save_token(token)
        return token['access_token']
    else:
        raise Exception("Failed to refresh access token")

# Fungsi untuk mengumpulkan informasi produk dari Amazon berdasarkan ASIN
def scrape_amazon(asin, store_id):
    product_link = f"https://www.amazon.com/dp/{asin}?tag={store_id}"

    response = requests.get(product_link)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        name = soup.select_one('#productTitle')
        price_whole = soup.select_one('.a-price-whole')
        price_fraction = soup.select_one('.a-price-fraction')
        image = soup.select_one('#imgTagWrapperId img')
        description = soup.select_one('#productDescription')
        features = soup.select_one('#feature-bullets')

        if name and price_whole and price_fraction and image and description and features:
            product_name = name.text.strip()
            product_price = f"${price_whole.text.strip()}.{price_fraction.text.strip()}"
            product_price = product_price.replace('..', '.')
            product_image = image['src']
            product_description = description.get_text(separator=" ").strip()
            product_features = '\n'.join(li.get_text(separator=" ").strip() for li in features.select('li'))

            product_url = f"https://www.amazon.com/dp/{asin}?tag={store_id}"

            return {
                "name": product_name,
                "price": product_price,
                "image": product_image,
                "description": product_description,
                "additional_description": product_features,
                "product_link": product_url
            }
        else:
            return {"error": "Detail produk tidak lengkap"}
    else:
        return {"error": f"Failed to retrieve the page for product URL: {product_link}. Status code: {response.status_code}"}

# Fungsi untuk mengirim posting ke blog
def create_blog_post(blog_id, title, content, labels):
    try:
        access_token = load_token()['access_token']
    except (KeyError, TypeError):
        access_token = refresh_access_token()
    
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    post_data = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": title,
        "content": content,
        "labels": labels
    }
    response = requests.post(url, headers=headers, json=post_data)
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.text}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_token')
def submit_token():
    return render_template('submit_token.html')

@app.route('/post_to_blog', methods=['POST'])
def post_to_blog():
    data = request.get_json()
    asins = data.get('asins')
    store_id = data.get('store_id')
    blog_id = data.get('blog_id')
    
    results = []
    for asin in asins:
        product_info = scrape_amazon(asin, store_id)
        
        if "error" in product_info:
            results.append({asin: product_info})
            continue
        
        title = product_info["name"]
        content = (
            f"<h1>{product_info['name']}</h1>"
            f"<img src='{product_info['image']}' alt='{product_info['name']}'>"
            f"<br /><strong>Price: {product_info['price']}   <a href='{product_info['product_link']}'>Buy on Amazon</a></strong>"
            f"<h2>Description</h2>"
            f"<p>{product_info['description']}</p>"
            f"<h2>Feature & Details</h2>"
            "<ul>"
            + "".join(f"<li>{feature.strip()}</li>" for feature in product_info['additional_description'].split("\n") if feature.strip())
            + "</ul>"
        )
        labels = ["Produk", "Amazon"]
        
        result = create_blog_post(blog_id, title, content, labels)
        results.append({asin: result})
    
    return jsonify(results)

@app.route('/update_token', methods=['POST'])
def update_token():
    data = request.get_json()
    save_token(data)
    return jsonify({"message": "Token updated successfully"})

if __name__ == '__main__':
    app.run(debug=True)