   def process_customer(customer_id):
       customer = get_customer(customer_id)
       return send_receipt(customer.email)
