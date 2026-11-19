	// CreateService and UpdateService omit tags. The generated merger treats
	// that as an empty tag set and clears Spec.Tags. Keep the desired tags.
	if ko.Spec.Tags == nil {
		ko.Spec.Tags = desired.ko.Spec.Tags
	}
