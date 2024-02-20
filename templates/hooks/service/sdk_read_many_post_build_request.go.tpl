	if r.ko.Spec.Name != nil {
		input.SetServices([]*string{r.ko.Spec.Name})
	}
	if r.ko.Spec.Cluster != nil {
		input.SetCluster(*r.ko.Spec.Cluster)
	}
	input.Include = []*string{
		aws.String("TAGS"),
	}