	// If the Tags field has changed, sync the tags with the AWS resource
	if delta.DifferentAt("Spec.Tags") {
		err := rm.syncTags(
			ctx,
			latest,
			desired,
		)
		if err != nil {
			return nil, err
		}
	}
	
	// If the only difference is in the Tags field, we don't need to make an update API call
	if !delta.DifferentExcept("Spec.Tags") {
		return desired, nil
	}