	if len(resp.Services) > 0 {
		if *resp.Services[0].Status == ServiceStatusInactive {
			return nil, ackerr.NotFound
		}
		if *resp.Services[0].Status == ServiceStatusDraining {
			return nil, requeueWaitWhileDraining
		}
	}