	// CreateService and UpdateService responses don't include tags, so the
	// generated SetOutput leaves Spec.Tags empty. Keep the desired tags;
	// ReadOne fills in the real ones.
	if len(ko.Spec.Tags) == 0 {
		ko.Spec.Tags = desired.ko.Spec.Tags
	}
