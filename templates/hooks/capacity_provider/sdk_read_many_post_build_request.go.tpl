	input.CapacityProviders = []string{*r.ko.Spec.Name}
	input.Include = []svcsdktypes.CapacityProviderField{
		svcsdktypes.CapacityProviderFieldTags,
	}
