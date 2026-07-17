import requests

# Fetch all cards
response = requests.get("https://arkhamdb.com/api/public/cards/")
all_cards = response.json()

# Filter for the Dunwich Cycle
# Using int(2) or str('2') handles potential data type variations
dwl_cycle_cards = [
    card for card in all_cards 
    if str(card.get('cycle_code')) == '2'
]

# Verify the count
print(f"Total cards found in Dunwich Cycle: {len(dwl_cycle_cards)}")
print("-" * 50)
print(f"{'ID':<10} | {'Quantity':<8} | {'Name'}")
print("-" * 50)

for card in dwl_cycle_cards:
    code = card.get('code')
    name = card.get('name')
    qty = card.get('quantity', 0)
    print(f"{code:<10} | {qty:<8} | {name}")