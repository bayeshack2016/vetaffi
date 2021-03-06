var _ = require('lodash');
var bulk = require('bulk-require');
var Claim = require('./../models/claim');
var expressions = require("angular-expressions");
var Form = require('./../models/form');
var http = require('http-status-codes');
var httpErrors = require('./../utils/httpErrors');
var Q = require('q');
var log = require('../middlewares/log');

var formlyFields = bulk(__dirname + '/../forms/', ['*']);

function ClaimService(app) {
  this.app = app;
}

module.exports = ClaimService;

/**
 * For a given form and set of responses, calculate how many questions
 * were answered (which is simply the number of keys in the responses),
 * and more complicatedly: how many questions on the form were answerable,
 * which requires evaluating the angular hideExpression attribute for
 * each field against the current responses.
 *
 * @param template Formly template from winterfell/forms
 * @param data Object with form responses.
 * @returns {requiredQuestions: number,
 *           optionalQuestions: number,
 *           answeredRequired: number,
 *           answeredOptional: number}
 */
function calculateProgress(template, data) {
  var evaluate, i;
  var output = {
    requiredQuestions: 1, // Signature always answerable
    answeredRequired: 0,
    optionalQuestions: 0,
    answeredOptional: 0
  };

  if (!template) {
    return output;
  }

  for (i = 0; i < template.fields.length; i++) {
    var field = template.fields[i];


    if (field.hasOwnProperty('hideExpression')) {
      evaluate = expressions.compile(field.hideExpression);
      if (!evaluate({model: data})) {
        if (field.templateOptions.optional) {
          output.optionalQuestions += 1;
        } else {
          output.requiredQuestions += 1;
        }
      }
    } else {
      if (field.templateOptions.optional) {
        output.optionalQuestions += 1;
      } else {
        output.requiredQuestions += 1;
      }
    }

    if (data.hasOwnProperty(field.key) && data[field.key] !== '') {
      if (field.templateOptions.optional) {
        output.answeredOptional += 1;
      } else {
        output.answeredRequired += 1;
      }
    }
  }

  if (data.signature) {
    output.answeredRequired += 1;
  }

  log.info('Calculated progress: optionalQuestions=' + output.optionalQuestions +
  ' requiredQuestions=' + output.requiredQuestions +
  ' answeredOptional=' + output.answeredOptional +
  ' answeredRequired=' + output.answeredRequired);

  return output;
}

module.exports.calculateProgress = calculateProgress;

module.exports.findIncompleteClaimOrCreate = function (userId, forms, callback) {
  return Claim.findOne({userId: userId, state: Claim.State.INCOMPLETE}).exec(function (err, fileClaim) {
    if (err) {
      callback(err, null);
    } else if (_.isEmpty(fileClaim)) {
      Claim.quickCreate(userId, function (err, claim) {
        if (err) {
          callback(err, null);
          return;
        }
        // Create all the forms and don't call the callback
        // until this is done by using a promise chain.
        var promise = Q();
        forms.forEach(function (form) {
          console.log("Creating form " + form);
          var progress = calculateProgress(formlyFields[form], {});
          promise = promise.then(function () {
            return Form.create({
              key: form,
              user: userId,
              responses: {},
              claim: claim._id,
              optionalQuestions: progress.optionalQuestions,
              requiredQuestions: progress.requiredQuestions,
              answeredRequired: progress.answeredRequired,
              answeredOptional: progress.answeredOptional
            });
          })
        });
        promise.then(function () {
          callback(null, claim);
        });
        promise.catch(function () {
          callback(err, null);
        });
      })
    } else {
      callback(null, fileClaim)
    }
  });
};

module.exports.setClaimState = function (claimId, state, callback) {
  var query = {_id: claimId};
  var update = {state: state};
  return Claim.update(query, update, callback);
};
