	// CapacityProvider resources continue to be returned after deletion with an INACTIVE state.
	// Return NotFound to allow for recreation of resource after deletion. 
	if ko.Status.Status != nil && *ko.Status.Status == "INACTIVE" {
		return nil, ackerr.NotFound
	}
