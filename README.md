# CISC-327-Group-5

**POST /rentals — Check out equipment**

Creates a rental for the specified renter and equipment. Equipment must exist and be marked as available (`is_available: true`) to be checked out. If equipment is marked out of service, the endpoint returns HTTP 400 with an error message and does not create a rental or modify the equipment's available unit count.