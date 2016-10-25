import grequests

numRequests = 1

elb = ""
input = {"job_id":7044}

reqs = (grequests.post(elb, **input) for i in range(numRequests))
resp = grequests.map(reqs)