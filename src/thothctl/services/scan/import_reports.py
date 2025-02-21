"""Import reports."""
import os
from gt_defect_dojo import defectdojo_apiv2


# setup DefectDojo connection information
host = "http://localhost:8080/"
api_key = os.environ["API_KEY"]
user = os.environ["USER"]

# instantiate the DefectDojo api wrapper
dd = defectdojo_apiv2.DefectDojoAPIv2(host, api_key, user, debug=True)

# If you need to disable certificate verification, set verify_ssl to False.
# dd = defectdojo.DefectDojoAPI(host, api_key, user, verify_ssl=False)

# Create a product
prod_type = 1  # 1 - Research and Development, product type
product = dd.create_product(
    "API Product Test", "This is a detailed product description.", prod_type
)

if product.success:
    # Get the product id
    product_id = product.id()
    print("Product successfully created with an id: " + str(product_id))

# List Products
products = dd.list_products()

if products.success:
    print(products.data_json(pretty=True))  # Decoded JSON object

    for product in products.data["objects"]:
        print(product["name"])  # Print the name of each product
else:
    print(products.message)
