	if ko.Status.Status != nil && *ko.Status.Status == "INACTIVE" {
		return nil, ackerr.NotFound
	}
