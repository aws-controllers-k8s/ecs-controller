	if r.ko.Spec.Name != nil {
		input.Services = []string{*r.ko.Spec.Name}
	}
	if r.ko.Spec.Cluster != nil {
		input.Cluster = r.ko.Spec.Cluster
	}
	input.Include = []svcsdktypes.ServiceField{
		svcsdktypes.ServiceFieldTags,
	}