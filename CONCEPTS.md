# Tracktion concepts

## Vehicle documents and storage

### Storage Profile
A Storage Profile is the durable description of one document-storage backend and its configuration; the application expects one profile to be active as the destination for new objects and expects each stored document to remain associated with the profile that owns its object.

Changing the active profile must not strand existing documents. A storage migration copies and verifies referenced objects before atomically changing ownership, and cleanup occurs only after references no longer depend on the source.

### Vehicle Photo
A Vehicle Photo is a document associated with a vehicle and classified for image display rather than general maintenance-document use.

### Primary Photo
A Primary Photo is the Vehicle Photo selected as a vehicle's representative image; deleting it selects another associated Vehicle Photo when one exists, otherwise the vehicle has no Primary Photo.
