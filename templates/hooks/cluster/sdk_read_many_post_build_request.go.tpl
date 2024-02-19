	input.Clusters = []*string{r.ko.Spec.Name}
	input.Include = []*string{
		aws.String("ATTACHMENTS"),
		aws.String("CONFIGURATIONS"),
		aws.String("SETTINGS"),
		aws.String("STATISTICS"),
		aws.String("TAGS"),
	}