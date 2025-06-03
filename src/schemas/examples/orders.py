create_order_example_schema = {
    "id": 2,
    "created_at": "2025-05-23T08:08:49.805Z",
    "movies": ["The Shawshank Redemption", "The Dark Knight"],
    "total_amount": "33.24",
    "status": "pending",
    "detail": "Movies from the cart added to the order successfully. Movies "
    "with the following IDs: [789] have not been added to the order "
    "because they are already in your other orders awaiting payment.",
}

response_list_orders_example_schema = {
    "orders": [create_order_example_schema],
}
