	input.Clusters = []string{*r.ko.Spec.Name}
	input.Include = []svcsdktypes.ClusterField{
		svcsdktypes.ClusterFieldAttachments,
		svcsdktypes.ClusterFieldConfigurations,
		svcsdktypes.ClusterFieldSettings,
		svcsdktypes.ClusterFieldStatistics,
		svcsdktypes.ClusterFieldTags,
	}