	if desired.ko.Spec.Name != nil {
		input.Service = desired.ko.Spec.Name
	}
	// ECS requires ForceNewDeployment when modifying the capacity provider
	// strategy on an existing service, otherwise the API returns
	// InvalidParameterException.
	if delta.DifferentAt("Spec.CapacityProviderStrategy") {
		input.ForceNewDeployment = true
	}
