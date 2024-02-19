    // Behind the scenes of ECS - when you delete an existing cluster, it
    // status will be set to INACTIVE and the resource will remain "existing"
    // for some time. As you might understand from the Go snipet below, yes,
    // we can "create" cluster that already exists (but are in INACTIVE) state.
    //
    // From ECS docs, INACTIVE: The cluster has been deleted. Clusters with an
    // INACTIVE status may remain discoverable in your account for a period of 
    // time. However, this behavior is subject to change in the future. We don't
    // recommend that you rely on INACTIVE clusters persisting.
    //
    // Possible statuses: ACTIVE, PROVISIONING, DEPROVISIONING, FAILED, INACTIVE
	if ko.Status.Status != nil && *ko.Status.Status == "INACTIVE" {
        // Returning a NotFound error will trigger the create path.
		return nil, ackerr.NotFound
	}