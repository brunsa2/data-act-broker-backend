from datetime import datetime
from unittest.mock import Mock
from dataactcore.models.jobModels import Submission, Job, FileGenerationTask
from dataactcore.models.baseInterface import BaseInterface
from dataactcore.interfaces.interfaceHolder import InterfaceHolder
from dataactcore.scripts.setupAllDB import setupAllDB
from dataactbroker.handlers.fileHandler import FileHandler

def st_start_generation_job(database):
    print("start generation test called")
    interfaces = InterfaceHolder()
    print("DB name is {}".format(BaseInterface.dbName))
    # Set up DBs
    setupAllDB()
    fileHandler = FileHandler(None,interfaces,True)
    # Mock D file API
    fileHandler.call_d_file_api = Mock(return_value=True)
    # Mock request object
    fileHandler.request = MockRequest()
    file_type = "D2"
    file_type_name = "award"
    sub, uploadJob, validationJob = setupSubmission(interfaces, file_type_name)
    print("Submission {}".format(sub.submission_id))
    submissions = interfaces.jobDb.session.query(Submission).all()
    print(str([sub.submission_id for sub in submissions]))
    success, errorResponse = fileHandler.startGenerationJob(sub.submission_id, file_type)
    assert(success)
    # Get file generation task created
    task = interfaces.jobDb.query(FileGenerationTask).filter(FileGenerationTask.submission_id == sub.submission_id).filter(FileGenerationTask.file_type_id == interfaces.jobDb.getFileTypeId(file_type_name)).one()
    assert(task.job_id == uploadJob.job_id)
    assert(uploadJob.job_status_id == interfaces.jobDb.getJobStatusId("running"))

    # Mock an empty response
    fileHandler.call_d_file_api = Mock(return_value=True)
    sub, uploadJob, validationJob = setupSubmission(interfaces, file_type_name)
    success, errorResponse = fileHandler.startGenerationJob(sub.submission_id, file_type)
    assert(success)
    task = interfaces.jobDb.query(FileGenerationTask).filter(FileGenerationTask.submission_id == sub.submission_id).filter(FileGenerationTask.file_type_id == interfaces.jobDb.getFileTypeId(file_type_name)).one()
    assert(task.job_id == uploadJob.job_id)
    assert(uploadJob.filename == "#")
    assert(uploadJob.job_status_id == interfaces.jobDb.getJobStatusId("finished"))

def setupSubmission(interfaces, file_type_name):
    """ Create a submission with jobs for specified file type """
    # Create test submission
    sub = Submission(datetime_utc=datetime.utcnow(), user_id=1, cgac_code = "SYS", reporting_start_date = "01/01/2016", reporting_end_date = "01/31/2016")
    interfaces.jobDb.session.commit()
    # Add jobs
    uploadJob = Job(job_status_id = interfaces.jobDb.getJobStatusId("ready"), job_type_id = interfaces.jobDb.getJobTypeId("file_upload"),
                    submission_id = sub.submission_id, file_type_id = interfaces.jobDb.getFileTypeId(file_type_name))
    validationJob =  Job(job_status_id = interfaces.jobDb.getJobStatusId("ready"), job_type_id = interfaces.jobDb.getJobTypeId("csv_record_validation"),
                    submission_id = sub.submission_id, file_type_id = interfaces.jobDb.getFileTypeId(file_type_name))
    interfaces.jobDb.session.add(uploadJob)
    interfaces.jobDb.session.add(validationJob)
    interfaces.jobDb.session.commit()
    return sub, uploadJob, validationJob

class MockRequest:

    def __init__(self):
        self.headers = {"Content-Type": "application/x-www-form-urlencoded"}
        self.form = {"start": "10/1/2016", "end": "12/31/2016"}


from unittest.mock import Mock

from dataactbroker.handlers import fileHandler
from dataactcore.interfaces.interfaceHolder import InterfaceHolder
from dataactcore.models import lookups
from dataactcore.models.jobModels import FileType, JobStatus, JobType
from tests.unit.dataactcore.factories.job import JobFactory


def test_start_generation_job_d2(database, monkeypatch, job_constants):
    sess = database.session
    job = JobFactory(
        job_status=sess.query(JobStatus).filter_by(name='waiting').one(),
        job_type=sess.query(JobType).filter_by(name='file_upload').one(),
        file_type=sess.query(FileType).filter_by(name='award').one(),
    )
    sess.add(job.submission)    # @todo: why is this needed?
    sess.add(job)
    sess.commit()

    # @todo: Is there a library that'd do this for us?
    request = Mock(
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        form={'start': '2010-01-01', 'end': '2010-02-01'}
    )
    handler = fileHandler.FileHandler(request, InterfaceHolder(),
                                      isLocal=True)
    handler.debug_file_name = 'my-file-name'    # @todo why isn't this set?
    monkeypatch.setattr(fileHandler, 'LoginSession',
                        Mock(getName=Mock(return_value=123)))
    handler.addJobInfoForDFile = Mock()
    result = handler.startGenerationJob(job.submission.submission_id, 'D2')

    sess.refresh(job)
    assert job.job_status_id == lookups.JOB_STATUS_DICT['running']

    assert result == handler.addJobInfoForDFile.return_value
    # Can verify args here
    # call_args = handler.addJobInfoForDFile.call_args[0]
