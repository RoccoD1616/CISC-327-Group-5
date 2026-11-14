import pytest
from datetime import date, timedelta

def test_create_renter(client):
    response = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })

    assert response.status_code == 201
    renter = response.get_json()
    assert renter["name"] == "John Smith"
    assert renter["email"] == "john@example.com"
    
def test_list_renters(client):
    # Create two renters
    client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })

    client.post("/renters", json={
        "name": "Jane Doe",
        "email": "jane@example.com"
    })

    # Retrieve the list of renters
    response = client.get("/renters")

    assert response.status_code == 200

    data = response.get_json()

    # Check that both renters are returned
    assert len(data) == 2
    assert any(r["name"] == "John Smith" for r in data)
    assert any(r["name"] == "Jane Doe" for r in data)
    
def test_retrieve_renter(client):
    # Create a renter
    create_response = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })

    assert create_response.status_code == 201

    renter = create_response.get_json()
    renter_id = renter["id"]

    # Retrieve the renter using their ID
    response = client.get(f"/renters/{renter_id}")

    assert response.status_code == 200

    data = response.get_json()

    # Verify that the correct renter was retrieved
    assert data["id"] == renter_id
    assert data["name"] == "John Smith"
    assert data["email"] == "john@example.com"


def test_retrieve_nonexistent_renter(client):
    # Attempt to retrieve a renter that does not exist
    response = client.get("/renters/99999")

    assert response.status_code == 404
    
def test_update_renter(client):
    # Create a renter
    create_response = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })

    assert create_response.status_code == 201

    renter = create_response.get_json()
    renter_id = renter["id"]

    # Update the renter's details
    response = client.put(f"/renters/{renter_id}", json={
        "name": "John Doe",
        "email": "johndoe@example.com"
    })

    assert response.status_code == 200

    # Retrieve the updated renter
    get_response = client.get(f"/renters/{renter_id}")

    assert get_response.status_code == 200

    data = get_response.get_json()

    # Verify that the details were updated
    assert data["id"] == renter_id
    assert data["name"] == "John Doe"
    assert data["email"] == "johndoe@example.com"


def test_update_nonexistent_renter(client):
    # Attempt to update a renter that does not exist
    response = client.put("/renters/99999", json={
        "name": "Jane Doe",
        "email": "jane@example.com"
    })

    assert response.status_code == 404
    
def test_delete_renter(client):
    # Create a renter
    create_response = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })
    assert create_response.status_code == 201
    renter = create_response.get_json()
    renter_id = renter["id"]
    # Delete the renter
    response = client.delete(f"/renters/{renter_id}")
    assert response.status_code == 204
    # Verify that the renter no longer exists
    get_response = client.get(f"/renters/{renter_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_renter(client):
    # Attempt to delete a renter that does not exist
    response = client.delete("/renters/99999")
    assert response.status_code == 404
    
def test_checkout_equipment(client):
    # Create equipment
    equipment_response = client.post("/equipment", json={
        "name": "Test Kayak",
        "category": "Water Sports",
        "total_units": 2,
        "is_available": True
    })
    assert equipment_response.status_code == 201
    equipment = equipment_response.get_json()
    equipment_id = equipment["id"]
    # Create renter
    renter_response = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })
    assert renter_response.status_code == 201
    renter = renter_response.get_json()
    renter_id = renter["id"]
    # Check out the equipment
    checkout_response = client.post("/rentals", json={
        "equipment_id": equipment_id,
        "renter_id": renter_id,
        "deposit_amount": 50
    })
    assert checkout_response.status_code == 201
    rental = checkout_response.get_json()
    # Verify rental details
    assert rental["equipment_id"] == equipment_id
    assert rental["renter_id"] == renter_id
    assert rental["deposit_amount"] == 50
    assert rental["return_date"] is None
    assert rental["due_date"] is not None
    # Verify that equipment availability decreased
    availability_response = client.get(
        f"/equipment/{equipment_id}/availability"
    )
    assert availability_response.status_code == 200
    availability = availability_response.get_json()
    assert availability["available_units"] == 1
    assert availability["total_units"] == 2
    # Verify that the rental was recorded
    rentals_response = client.get("/rentals")
    assert rentals_response.status_code == 200
    rentals = rentals_response.get_json()
    assert any(
        r["equipment_id"] == equipment_id
        and r["renter_id"] == renter_id
        for r in rentals
    )
    
def test_checkout_nonexistent_equipment(client):
    # Create a renter
    renter_response = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })
    renter_id = renter_response.get_json()["id"]
    # Attempt to check out nonexistent equipment
    response = client.post("/rentals", json={
        "equipment_id": 99999,
        "renter_id": renter_id,
        "deposit_amount": 50
    })

    assert response.status_code == 404
    
def test_checkout_out_of_service_equipment(client):
    equipment_response = client.post("/equipment", json={
        "name": "Broken Drill",
        "category": "Power Tools",
        "total_units": 2,
        "is_available": False
    })
    assert equipment_response.status_code == 201
    equipment_id = equipment_response.get_json()["id"]
    renter_response = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })
    assert renter_response.status_code == 201
    renter_id = renter_response.get_json()["id"]
    response = client.post("/rentals", json={
        "equipment_id": equipment_id,
        "renter_id": renter_id,
        "due_date": "2026-11-10"
    })

    assert response.status_code == 400
    
def test_list_rentals(client):
    # Create equipment
    equipment = client.post("/equipment", json={
        "name": "Test Kayak",
        "category": "Water Sports",
        "total_units": 2,
        "is_available": True
    }).get_json()

    # Create renter
    renter = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    }).get_json()

    # Create a rental
    client.post("/rentals", json={
        "equipment_id": equipment["id"],
        "renter_id": renter["id"],
        "deposit_amount": 50
    })

    # Retrieve all rentals
    response = client.get("/rentals")

    assert response.status_code == 200

    rentals = response.get_json()

    # Verify that the rental was returned
    assert len(rentals) == 1
    assert rentals[0]["equipment_id"] == equipment["id"]
    assert rentals[0]["renter_id"] == renter["id"]
    
def test_filter_rentals_by_equipment(client):
    # Create two equipment items
    equipment1 = client.post("/equipment", json={
        "name": "Test Kayak",
        "category": "Water Sports",
        "total_units": 2,
        "is_available": True
    }).get_json()

    equipment2 = client.post("/equipment", json={
        "name": "Test Canoe",
        "category": "Water Sports",
        "total_units": 2,
        "is_available": True
    }).get_json()

    # Create a renter
    renter = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    }).get_json()

    # Create rentals for both equipment items
    client.post("/rentals", json={
        "equipment_id": equipment1["id"],
        "renter_id": renter["id"]
    })

    client.post("/rentals", json={
        "equipment_id": equipment2["id"],
        "renter_id": renter["id"]
    })

    # Filter rentals by the first equipment ID
    response = client.get(
        f"/rentals?equipment_id={equipment1['id']}"
    )

    assert response.status_code == 200

    rentals = response.get_json()

    assert len(rentals) == 1
    assert rentals[0]["equipment_id"] == equipment1["id"]

def test_filter_rentals_by_renter(client):
    # Create two equipment items
    equipment1 = client.post("/equipment", json={
        "name": "Extension Ladder",
        "category": "Climbing",
        "total_units": 2
    }).get_json()

    equipment2 = client.post("/equipment", json={
        "name": "Power Drill",
        "category": "Tools",
        "total_units": 2
    }).get_json()

    # Create two renters
    renter1 = client.post("/renters", json={
        "name": "Jane Smith",
        "email": "jane@example.com"
    }).get_json()

    renter2 = client.post("/renters", json={
        "name": "John Doe",
        "email": "john@example.com"
    }).get_json()

    # Create a rental for each renter
    rental1 = client.post("/rentals", json={
        "equipment_id": equipment2["id"],
        "renter_id": renter1["id"]
    })
    assert rental1.status_code == 201

    rental2 = client.post("/rentals", json={
        "equipment_id": equipment1["id"],
        "renter_id": renter2["id"]
    })
    assert rental2.status_code == 201

    # Filter rentals using the first renter's ID
    response = client.get(
        f"/rentals?renter_id={renter1['id']}"
    )

    assert response.status_code == 200
    rentals = response.get_json()

    assert len(rentals) == 1
    assert rentals[0]["renter_id"] == renter1["id"]
    
def test_return_equipment(client):
    # Create equipment
    equipment_response = client.post("/equipment", json={
        "name": "Test Kayak",
        "category": "Water Sports",
        "total_units": 2,
        "is_available": True
    })

    equipment_id = equipment_response.get_json()["id"]

    # Create renter
    renter_response = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    })

    renter_id = renter_response.get_json()["id"]

    # Check out equipment
    checkout_response = client.post("/rentals", json={
        "equipment_id": equipment_id,
        "renter_id": renter_id
    })

    assert checkout_response.status_code == 201

    rental_id = checkout_response.get_json()["id"]

    # Return the equipment
    return_response = client.put(
        f"/rentals/{rental_id}/return"
    )

    assert return_response.status_code == 200

    # Verify that the rental has been marked as returned
    rental_response = client.get(f"/rentals")
    rentals = rental_response.get_json()

    returned_rental = next(
        r for r in rentals if r["id"] == rental_id
    )

    assert returned_rental["return_date"] is not None

    # Verify that equipment availability was restored
    availability_response = client.get(
        f"/equipment/{equipment_id}/availability"
    )

    availability = availability_response.get_json()

    assert availability["available_units"] == 2
    assert availability["total_units"] == 2
    
def test_return_nonexistent_rental(client):
    # Attempt to return a rental that does not exist
    response = client.put("/rentals/99999/return")

    assert response.status_code == 404

def test_return_equipment_twice(client):
    # Create equipment
    equipment = client.post("/equipment", json={
        "name": "Test Kayak",
        "category": "Water Sports",
        "total_units": 2,
        "is_available": True
    }).get_json()

    # Create renter
    renter = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    }).get_json()

    # Check out equipment
    checkout_response = client.post("/rentals", json={
        "equipment_id": equipment["id"],
        "renter_id": renter["id"]
    })

    rental_id = checkout_response.get_json()["id"]

    # Return equipment for the first time
    first_return = client.put(
        f"/rentals/{rental_id}/return"
    )

    assert first_return.status_code == 200

    # Attempt to return the same equipment again
    second_return = client.put(
        f"/rentals/{rental_id}/return"
    )

    assert second_return.status_code == 400

def test_release_deposit(client):
    equipment_response = client.post("/equipment", json={
        "name": "Camera",
        "category": "Electronics",
        "total_units": 1
    })
    assert equipment_response.status_code == 201
    equipment_id = equipment_response.get_json()["id"]

    renter_response = client.post("/renters", json={
        "name": "Jane Smith",
        "email": "jane@example.com"
    })
    assert renter_response.status_code == 201
    renter_id = renter_response.get_json()["id"]

    rental_response = client.post("/rentals", json={
        "equipment_id": equipment_id,
        "renter_id": renter_id,
        "due_date": "2026-11-10",
        "deposit_amount": 100
    })
    assert rental_response.status_code == 201
    rental_id = rental_response.get_json()["id"]

    return_response = client.put(f"/rentals/{rental_id}/return")
    assert return_response.status_code == 200

    release_response = client.put(
        f"/rentals/{rental_id}/deposit/release"
    )
    assert release_response.status_code == 200
    assert release_response.get_json()["deposit_released"] is True

    rentals_response = client.get("/rentals")
    assert rentals_response.status_code == 200

    rentals = rentals_response.get_json()
    rental = next(r for r in rentals if r["id"] == rental_id)

    assert rental["deposit_released"] is True
    
def test_release_deposit_before_return(client):
    # Create equipment
    equipment = client.post("/equipment", json={
        "name": "Test Kayak",
        "category": "Water Sports",
        "total_units": 2,
        "is_available": True
    }).get_json()

    # Create renter
    renter = client.post("/renters", json={
        "name": "John Smith",
        "email": "john@example.com"
    }).get_json()

    # Check out equipment with a deposit
    checkout_response = client.post("/rentals", json={
        "equipment_id": equipment["id"],
        "renter_id": renter["id"],
        "deposit_amount": 50
    })

    rental_id = checkout_response.get_json()["id"]

    # Attempt to release the deposit before returning equipment
    response = client.put(
        f"/rentals/{rental_id}/deposit/release"
    )

    assert response.status_code == 400

