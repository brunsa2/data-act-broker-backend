import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from dataactcore.models.errorModels import ErrorMetadata, File
from dataactcore.models.jobModels import Job, Submission, JobDependency
from dataactcore.models.stagingModels import AwardFinancial
from dataactcore.models.userModel import User, UserStatus, EmailTemplateType, EmailTemplate, PermissionType
from dataactcore.models.validationModels import RuleSeverity
from dataactcore.models.lookups import (FILE_TYPE_DICT, FILE_STATUS_DICT, JOB_TYPE_DICT,
                                        JOB_STATUS_DICT, FILE_TYPE_DICT_ID, PERMISSION_TYPE_DICT)
from dataactcore.interfaces.db import GlobalDB
from dataactvalidator.validation_handlers.validationError import ValidationError


# First step to deprecating BaseInterface, its children, and corresponding
# interface holders is to start moving all db access logic into one big
# file (to prevent circular imports and have everything in the same place).
# Still to do...make this work solely with a flask context...original idea
# was that these functions would only be invoked within a Flask route, but
# there are some (e.g., createUserWithPassword) that need to be here,
# pending a further refactor.
# As a temporary measure, until the next part of the work that refactors
# the db access within Flask requests, fire up an ad-hoc db session in
# these transitional functions.


# todo: move these value to config if it is decided to keep local user login long term
HASH_ROUNDS = 12


def createUserWithPassword(email, password, bcrypt, permission=1, cgac_code="SYS"):
    """Convenience function to set up fully-baked user (used for setup/testing only)."""
    sess = GlobalDB.db().session
    status = sess.query(UserStatus).filter(UserStatus.name == 'approved').one()
    user = User(email=email, user_status=status, permissions=permission,
                cgac_code=cgac_code, name='Administrator', title='System Admin')
    user.salt, user.password_hash = getPasswordHash(password, bcrypt)
    sess.add(user)
    sess.commit()

    return user


def getPasswordHash(password, bcrypt):
    """Generate password hash."""
    # TODO: handle password hashing/lookup in the User model
    salt = uuid.uuid4().hex
    # number 12 below iw the number of rounds for bcrypt
    hash = bcrypt.generate_password_hash(password + salt, HASH_ROUNDS)
    password_hash = hash.decode("utf-8")
    return salt, password_hash


def getUsersByType(permission_name):
    """Get list of users with specified permission."""
    sess = GlobalDB.db().session
    # This could likely be simplified, but since we're moving towards using MAX for authentication,
    # it's not worth spending too much time reworking.
    user_list = []
    bit_number = PERMISSION_TYPE_DICT[permission_name]
    users = sess.query(User).all()
    for user in users:
        if check_permission_by_bit_number(user, bit_number):
            # This user has this permission, include them in list
            user_list.append(user)
    return user_list


def check_permission_by_bit_number(user, bit_number):
    """Check whether user has the specified permission, determined by whether a binary representation of user's
    permissions has the specified bit set to 1.  Use has_permission to check by permission name."""
    # This could likely be simplified, but since we're moving towards using MAX for authentication,
    # it's not worth spending too much time reworking.

    if user.permissions is None:
        # This user has no permissions
        return False
    # First get the value corresponding to the specified bit (i.e. 2^bitNumber)
    bit_value = 2 ** bit_number
    # Remove all bits above the target bit by modding with the value of the next higher bit
    # This leaves the target bit and all lower bits as the remaining value, all higher bits are set to 0
    low_end = user.permissions % (bit_value * 2)
    # Now compare the remaining value to the value for the target bit to determine if that bit is 0 or 1
    # If the remaining value is still at least the value of the target bit, that bit is 1, so we have that permission
    return low_end >= bit_value


def populateSubmissionErrorInfo(submissionId):
    """Set number of errors and warnings for submission."""
    sess = GlobalDB.db().session
    submission = sess.query(Submission).filter(Submission.submission_id == submissionId).one()
    submission.number_of_errors = sumNumberOfErrorsForJobList(submissionId)
    submission.number_of_warnings = sumNumberOfErrorsForJobList(submissionId, errorType='warning')
    sess.commit()


def sumNumberOfErrorsForJobList(submissionId, errorType='fatal'):
    """Add number of errors for all jobs in list."""
    sess = GlobalDB.db().session
    errorSum = 0
    jobs = sess.query(Job).filter(Job.submission_id == submissionId).all()
    for job in jobs:
        jobErrors = checkNumberOfErrorsByJobId(job.job_id, errorType)
        if errorType == 'fatal':
            job.number_of_errors = jobErrors
        elif errorType == 'warning':
            job.number_of_warnings = jobErrors
        errorSum += jobErrors
    sess.commit()
    return errorSum


def checkNumberOfErrorsByJobId(jobId, errorType='fatal'):
    """Get the number of errors for a specified job and severity."""
    sess = GlobalDB.db().session
    errors = sess.query(func.sum(ErrorMetadata.occurrences)).\
        join(ErrorMetadata.severity).\
        filter(ErrorMetadata.job_id == jobId, RuleSeverity.name == errorType).scalar()
    # error_metadata table tallies total errors by job/file/field/error type. jobs that
    # don't have errors or warnings won't be in the table at all. thus, if the above query
    # returns an empty value that means the job didn't have any errors that matched
    # the specified severity type, so return 0
    return errors or 0


def addJobsForFileType(fileType, filePath, filename, submissionId, existingSubmission, jobsRequired, uploadDict):
    """ Add upload and validation jobs for a single filetype

    Args:
        fileType: What type of file to add jobs for
        filePath: Path to upload the file to
        filename: Original filename
        submissionId -- Submission ID to attach to jobs
        existingSubmission -- True if we should update existing jobs rather than creating new ones
        jobsRequired: List of job ids that will be prerequisites for cross-file job
        uploadDict: Dictionary of upload ids by filename to return to client, used for calling finalize_submission route

    Returns:
        jobsRequired: List of job ids that will be prerequisites for cross-file job
        uploadDict: Dictionary of upload ids by filename to return to client, used for calling finalize_submission route
    """
    sess = GlobalDB.db().session

    fileTypeId = FILE_TYPE_DICT[fileType]

    # Create a file upload job or, for an existing submission, modify the
    # existing upload job.

    if existingSubmission:
        # mark existing upload job as running
        uploadJob = sess.query(Job).filter_by(
            submission_id=submissionId,
            file_type_id=fileTypeId,
            job_type_id=JOB_TYPE_DICT['file_upload']
        ).one()
        # Mark as running and set new file name and path
        uploadJob.job_status_id = JOB_STATUS_DICT['running']
        uploadJob.original_filename = filename
        uploadJob.filename = filePath

    else:
        if fileType in ["award", "award_procurement"]:
            # file generation handled on backend, mark as ready
            uploadStatus = JOB_STATUS_DICT['ready']
        elif fileType in ["awardee_attributes", "sub_award"]:
            # these are dependent on file D2 validation
            uploadStatus = JOB_STATUS_DICT['waiting']
        else:
            # mark as running since frontend should be doing this upload
            uploadStatus = JOB_STATUS_DICT['running']

        uploadJob = Job(original_filename=filename, filename=filePath, file_type_id=fileTypeId,
                        job_status_id=uploadStatus, job_type_id=JOB_TYPE_DICT['file_upload'],
                        submission_id=submissionId)
        sess.add(uploadJob)

    sess.flush()

    # Create a file validation job or, for an existing submission, modify the
    # existing validation job.

    if existingSubmission:
        # if the file's validation job is attached to an existing submission,
        # reset its status and delete any validation artifacts (e.g., error metadata) that
        # might exist from a previous run.
        valJob = sess.query(Job).filter_by(
            submission_id=submissionId,
            file_type_id=fileTypeId,
            job_type_id=JOB_TYPE_DICT['csv_record_validation']
        ).one()
        valJob.job_status_id = JOB_STATUS_DICT['waiting']
        valJob.original_filename = filename
        valJob.filename = filePath
        # Reset file size and number of rows to be set during validation of new file
        valJob.file_size = None
        valJob.number_of_rows = None
        # Delete error metdata this might exist from a previous run of this validation job
        sess.query(ErrorMetadata).\
            filter(ErrorMetadata.job_id == valJob.job_id).\
            delete(synchronize_session='fetch')
        # Delete file error information that might exist from a previous run of this validation job
        sess.query(File).filter(File.job_id == valJob.job_id).delete(synchronize_session='fetch')

    else:
        # create a new record validation job and add dependencies if necessary
        if fileType == "awardee_attributes":
            d1ValJob = sess.query(Job).\
                filter(Job.submission_id == submissionId,
                       Job.file_type_id == FILE_TYPE_DICT['award_procurement'],
                       Job.job_type_id == JOB_TYPE_DICT['csv_record_validation']).\
                first()
            if d1ValJob is None:
                raise Exception("Cannot create E job without a D1 job")
            # Add dependency on D1 validation job
            d1Dependency = JobDependency(job_id=uploadJob.job_id, prerequisite_id=d1ValJob.job_id)
            sess.add(d1Dependency)

        elif fileType == "sub_award":
            # todo: check for C validation job
            cValJob = sess.query(Job). \
                filter(Job.submission_id == submissionId,
                       Job.file_type_id == FILE_TYPE_DICT['award_financial'],
                       Job.job_type_id == JOB_TYPE_DICT['csv_record_validation']). \
                first()
            if cValJob is None:
                raise Exception("Cannot create F job without a C job")
            # Add dependency on C validation job
            cDependency = JobDependency(job_id=uploadJob.job_id, prerequisite_id=cValJob.job_id)
            sess.add(cDependency)

        else:
            # E and F don't get validation jobs
            valJob = Job(original_filename=filename, filename=filePath, file_type_id=fileTypeId,
                         job_status_id=JOB_STATUS_DICT['waiting'],
                         job_type_id=JOB_TYPE_DICT['csv_record_validation'],
                         submission_id=submissionId)
            sess.add(valJob)
            sess.flush()
            # Add dependency between file upload and db upload
            uploadDependency = JobDependency(job_id=valJob.job_id, prerequisite_id=uploadJob.job_id)
            sess.add(uploadDependency)
            jobsRequired.append(valJob.job_id)

    sess.commit()

    uploadDict[fileType] = uploadJob.job_id
    return jobsRequired, uploadDict

""" ERROR DB FUNCTIONS """
def getErrorType(job_id):
    """ Returns either "none", "header_errors", or "row_errors" depending on what errors occurred during validation """
    sess = GlobalDB.db().session
    if sess.query(File).options(joinedload("file_status")).filter(
                    File.job_id == job_id).one().file_status.name == "header_error":
        # Header errors occurred, return that
        return "header_errors"
    elif sess.query(Job).filter(Job.job_id == job_id).one().number_of_errors > 0:
        # Row errors occurred
        return "row_errors"
    else:
        # No errors occurred during validation
        return "none"

def createFileIfNeeded(job_id, filename = None):
    """ Return the existing file object if it exists, or create a new one """
    sess = GlobalDB.db().session
    try:
        fileRec = sess.query(File).filter(File.job_id == job_id).one()
        # Set new filename for changes to an existing submission
        fileRec.filename = filename
    except NoResultFound:
        fileRec = createFile(job_id, filename)
    return fileRec

def createFile(job_id, filename):
    """ Create a new file object for specified job and filename """
    sess = GlobalDB.db().session
    try:
        int(job_id)
    except:
        raise ValueError("".join(["Bad job_id: ", str(job_id)]))

    fileRec = File(job_id=job_id,
                   filename=filename,
                   file_status_id=FILE_STATUS_DICT['incomplete'])
    sess.add(fileRec)
    sess.commit()
    return fileRec

def writeFileError(job_id, filename, error_type, extra_info=None):
    """ Write a file-level error to the file table

    Args:
        job_id: ID of job in job tracker
        filename: name of error report in S3
        error_type: type of error, value will be mapped to ValidationError class
        extra_info: list of extra information to be included in file
    """
    sess = GlobalDB.db().session
    try:
        int(job_id)
    except:
        raise ValueError("".join(["Bad jobId: ", str(job_id)]))

    # Get File object for this job ID or create it if it doesn't exist
    fileRec = createFileIfNeeded(job_id, filename)

    # Mark error type and add header info if present
    fileRec.file_status_id = FILE_STATUS_DICT[ValidationError.getErrorTypeString(error_type)]
    if extra_info is not None:
        if "missing_headers" in extra_info:
            fileRec.headers_missing = extra_info["missing_headers"]
        if "duplicated_headers" in extra_info:
            fileRec.headers_duplicated = extra_info["duplicated_headers"]

    sess.add(fileRec)
    sess.commit()

def markFileComplete(job_id, filename=None):
    """ Marks file's status as complete

    Args:
        job_id: ID of job in job tracker
        filename: name of error report in S3
    """
    sess = GlobalDB.db().session
    fileComplete = createFileIfNeeded(job_id, filename)
    fileComplete.file_status_id = FILE_STATUS_DICT['complete']
    sess.commit()

def getErrorMetricsByJobId(job_id, include_file_types=False, severity_id=None):
    """ Get error metrics for specified job, including number of errors for each field name and error type """
    sess = GlobalDB.db().session
    result_list = []

    query_result = sess.query(File).options(joinedload("file_status")).filter(File.job_id == job_id).one()

    if not query_result.file_status.file_status_id == FILE_STATUS_DICT['complete']:
        return [{"field_name": "File Level Error", "error_name": query_result.file_status.name,
                 "error_description": query_result.file_status.description, "occurrences": 1, "rule_failed": ""}]

    query_result = sess.query(ErrorMetadata).options(joinedload("error_type")).filter(
        ErrorMetadata.job_id == job_id, ErrorMetadata.severity_id == severity_id).all()
    for result in query_result:
        record_dict = {"field_name": result.field_name, "error_name": result.error_type.name,
                      "error_description": result.error_type.description, "occurrences": str(result.occurrences),
                      "rule_failed": result.rule_failed, "original_label": result.original_rule_label}
        if include_file_types:
            record_dict['source_file'] = FILE_TYPE_DICT_ID.get(result.file_type_id, '')
            record_dict['target_file'] = FILE_TYPE_DICT_ID.get(result.target_file_type_id, '')
        result_list.append(record_dict)
    return result_list

""" USER DB FUNCTIONS """
def get_email_template(email_type):
    """ Get template for specified email type
    Arguments:
        email_type - Name of template to get
    Returns:
        EmailTemplate object
    """
    sess = GlobalDB.db().session
    type_result = sess.query(EmailTemplateType.email_template_type_id).filter(EmailTemplateType.name == email_type).one()
    template_result = sess.query(EmailTemplate).filter(EmailTemplate.template_type_id == type_result.email_template_type_id).one()
    return template_result

def has_permission(user, permission_name):
    """ Checks if user has specified permission

    Arguments:
        user - User object
        permission_name - permission to check
    Returns:
        True if user has the specified permission, False otherwise
    """
    # Get the bit number corresponding to this permission from the PERMISSION_TYPE_DICT and use it to check whether
    # user has the specified permission
    if check_permission_by_bit_number(user, PERMISSION_TYPE_DICT[permission_name]):
        return True
    return False

def check_correct_password(user, password, bcrypt):
    """ Given a user object and a password, verify that the password is correct.

    Arguments:
        user - User object
        password - Password to check
        bcrypt - bcrypt to use for password hashing
    Returns:
         True if valid password, False otherwise.
    """
    if password is None or password.strip() == "":
        # If no password or empty password, reject
        return False

    # Check the password with bcrypt
    return bcrypt.check_password_hash(user.password_hash, password + user.salt)


def set_user_password(user, password, bcrypt):
    """ Given a user and a new password, changes the hashed value in the database to match new password.

    Arguments:
        user - User object
        password - password to be set
        bcrypt - bcrypt to use for password hashing
    Returns:
         True if successful
    """
    sess = GlobalDB.db().session
    # Generate hash with bcrypt and store it
    new_salt = uuid.uuid4().hex
    user.salt = new_salt
    password_hash = bcrypt.generate_password_hash(password + new_salt, HASH_ROUNDS)
    user.password_hash = password_hash.decode("utf-8")
    sess.commit()
    return True

def get_user_permission(user):
    """ Get name for specified permissions for this user

    Arguments:
        user
    Returns:
        array of permission names
    """
    user_permissions = []
    for permission_name in PERMISSION_TYPE_DICT:
        if has_permission(user, permission_name):
            user_permissions.append(permission_name)
    return sorted(user_permissions, key=str.lower)


def grant_permission(user, permission_name):
    """ Grant a user a permission specified by name, does not affect other permissions

    Arguments:
        user - User object
        permission_name - permission to grant
    """
    sess = GlobalDB.db().session
    if user.permissions is None:
        # Start users with zero permissions
        user.permissions = 0
    bit_number = PERMISSION_TYPE_DICT[permission_name]
    if not check_permission_by_bit_number(user, bit_number):
        # User does not have permission, grant it
        user.permissions += (2 ** bit_number)
        sess.commit()


def remove_permission(user, permission_name):
    """ Remove a permission specified by name from user

    Arguments:
        user - User object
        permissionName - permission to remove
    """
    sess = GlobalDB.db().session
    if user.permissions is None:
        # Start users with zero permissions
        user.permissions = 0
    bit_number = PERMISSION_TYPE_DICT[permission_name]
    if check_permission_by_bit_number(user, bit_number):
        # User has permission, remove it
        user.permissions -= (2 ** bit_number)
        sess.commit()


def get_submission_stats(submission_id):
    """Get summarized dollar amounts by submission."""
    sess = GlobalDB.db().session
    base_query = sess.query(func.sum(AwardFinancial.transaction_obligated_amou)).\
        filter(AwardFinancial.submission_id == submission_id)
    procurement = base_query.filter(AwardFinancial.piid != None)
    fin_assist = base_query.filter(or_(AwardFinancial.fain != None, AwardFinancial.uri != None))
    return {
        "total_obligations": float(base_query.scalar() or 0),
        "total_procurement_obligations": float(procurement.scalar() or 0),
        "total_assistance_obligations": float(fin_assist.scalar() or 0)
    }


def run_job_checks(job_id):
    """ Checks that specified job has no unsatisfied prerequisites
    Args:
        job_id -- job_id of job to be run

    Returns:
        True if prerequisites are satisfied, False if not
    """
    sess = GlobalDB.db().session

    # Get count of job's prerequisites that are not yet finished
    incomplete_dependencies = sess.query(JobDependency). \
        join("prerequisite_job"). \
        filter(JobDependency.job_id == job_id, Job.job_status_id != JOB_STATUS_DICT['finished']). \
        count()
    if incomplete_dependencies:
        return False
    else:
        return True
