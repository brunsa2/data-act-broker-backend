from dataactcore.models.validationInterface import ValidationInterface
from dataactcore.utils.statusCode import StatusCode
from dataactcore.utils.jsonResponse import JsonResponse

class ValidationHandler(ValidationInterface):
    """ Responsible for all interaction with the validation database

    Instance fields:
    engine -- sqlalchemy engine for generating connections and sessions
    connection -- sqlalchemy connection for executing direct SQL statements
    session -- sqlalchemy session for ORM usage
    """

    def listAgencies(self):
        agencies = self.validationManager.getAllAgencies()
        agency_list = []

        for agency in agencies:
            agency_list.append({"agency_name": agency.agency_name, "cgac_code": agency.cgac_code})

        return JsonResponse.create(StatusCode.OK, {"cgac_agency_list": agency_list})