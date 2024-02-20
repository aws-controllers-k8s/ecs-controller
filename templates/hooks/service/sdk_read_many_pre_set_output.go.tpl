	if len(resp.Services) > 0 {
		if *resp.Services[0].Status == "INACTIVE" {
			return nil, ackerr.NotFound
		}
		if *resp.Services[0].Status == "DRAINING" {
			return nil, ackrequeue.NeededAfter(nil, 1000*1000*1000*5)
		}
	}