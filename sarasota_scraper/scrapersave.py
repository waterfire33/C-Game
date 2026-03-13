import requests
from bs4 import BeautifulSoup
import csv
import re

def get_value_by_label(container, label_text):
    """Finds a label and grabs the value sitting right next to it."""
    label = container.find(lambda tag: tag.name in ["span", "td", "div"] 
                           and label_text.lower() in tag.get_text().lower())
    if not label: return "N/A"
    
    # Check immediate sibling first
    value_node = label.find_next_sibling(["span", "td", "div"])
    
    # Check parent's next sibling (common in Sarasota's table rows)
    if not value_node and label.parent:
        value_node = label.parent.find_next_sibling(["td", "div"])
    
    if value_node:
        return value_node.get_text(strip=True)
    
    return "N/A"

def search_sarasota_real_estate(street_name):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    url = "https://www.sc-pa.com/propertysearch/Result"
    payload = {"AddressKeywords": street_name.upper(), "search": "search"}
    
    print(f"\nSearching database for: {street_name.upper()}...")
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status() 
    except Exception as e:
        print(f"Connection Error: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Grab street name parts for broad keyword matching
    keyword = street_name.split()[0].upper()
    address_links = soup.find_all("a", string=lambda s: s and keyword in s.upper())
    
    # Identify property containers
    properties = soup.find_all("div", class_="resultl")

    results = []
    for i in range(len(properties)):
        prop = properties[i]
        
        # 1. Capture Address
        address = address_links[i].get_text(strip=True) if i < len(address_links) else "Unknown Address"
        
        # 2. Capture Owner
        owner = get_value_by_label(prop, "Ownership")
        
        # 3. Capture History (Price and Date)
        prop_text = prop.get_text()
        if any(msg in prop_text for msg in ["No associated qualified sale", "No sales associated"]):
            date, price = "No Sales", "No Sales"
        else:
            date = get_value_by_label(prop, "Transfer Date")
            price = get_value_by_label(prop, "Recorded Consideration")
            
            # Regex Fallbacks if labels shift
            if date == "N/A":
                date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}', prop_text)
                date = date_match.group(0) if date_match else "N/A"
            if price == "N/A":
                price_match = re.search(r'\$\d{1,3}(?:,\d{3})*', prop_text)
                price = price_match.group(0) if price_match else "N/A"

        # FIXED: Printing and Appending the full record
        print(f"FOUND: {address}")
        print(f"  OWNER: {owner}")
        print(f"  SOLD:  {date} for {price}")
        print("-" * 50)
        
        results.append({
            "Address": address, 
            "Owner": owner, 
            "Transfer Date": date, 
            "Price": price
        })

    return results

def save_to_csv(data, filename):
    if not data: return
    keys = data[0].keys() 
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)
    print(f"✅ Success! All data (Names + History) saved to: {filename}")

if __name__ == "__main__":
    print("==========================================")
    print("   SARASOTA PROPERTY RESEARCH TOOL v1.3   ")
    print("==========================================\n")

    while True:
        user_input = input("Please input street name (e.g., RITA ST): ").strip()
        if user_input.lower() in ['exit', 'quit', 'q']: break
        if not user_input: continue

        final_results = search_sarasota_real_estate(user_input)
        
        if final_results:
            filename = f"{user_input.replace(' ', '_').upper()}_results.csv"
            save_to_csv(final_results, filename)
        else:
            print(f"No results found for {user_input}.")
        print("\n" + "="*40 + "\n")