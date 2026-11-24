	// UpdateService does not change tags. Sync them with TagResource and
	// UntagResource, then skip UpdateService when tags are the only difference.
	if delta.DifferentAt("Spec.Tags") {
		if latest.ko.Status.ACKResourceMetadata == nil || latest.ko.Status.ACKResourceMetadata.ARN == nil {
			return nil, fmt.Errorf("service ARN is required to sync tags")
		}
		if err = syncTags(
			ctx, rm.sdkapi, rm.metrics,
			string(*latest.ko.Status.ACKResourceMetadata.ARN),
			desired.ko.Spec.Tags, latest.ko.Spec.Tags,
		); err != nil {
			return nil, err
		}
	}
	if !delta.DifferentExcept("Spec.Tags") {
		return desired, nil
	}
	if desired.ko.Spec.Name != nil {
		input.Service = desired.ko.Spec.Name
	}
	// ECS requires ForceNewDeployment when modifying the capacity provider
	// strategy on an existing service, otherwise the API returns
	// InvalidParameterException.
	if delta.DifferentAt("Spec.CapacityProviderStrategy") {
		input.ForceNewDeployment = true
	}
