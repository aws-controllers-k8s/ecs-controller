	// If Tags are specified, mark the resource as needing to be synced
	if ko.Spec.Tags != nil {
		// Setting Synced condition to false will trigger a requeue of the resource
		ackcondition.SetSynced(&resource{ko}, corev1.ConditionFalse, nil, nil)
	}