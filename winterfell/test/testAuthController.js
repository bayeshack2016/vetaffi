'use strict';
var http = require('http-status-codes');
var httpErrors = require('./../utils/httpErrors');
var should = require('should');
var session = require('supertest-session');
var uuid = require('uuid');
var User = require('../models/user');

describe('AuthController', function() {
  var targetUser;
  var server;
  var testSession;

  before(function() {
    server = require('../app');
    testSession = session(server);

    User.remove({}, function() {
      User.create({
        firstname: 'Sir',
        middlename: 'Moose',
        lastname: 'Alot',
        email: 'sirmoosealot@test.com',
        password: 'qwerasdf',
        externalId: uuid.v4(),
        state: User.State.ACTIVE
      }, function(err, user) {
        targetUser = user;
      });
    });
  });

  after(function () {
    server.close();
  });

  it('Log in success', function (done) {
    testSession.post('/auth/login')
      .send({email: targetUser.email, password: targetUser.password})
      .expect(http.OK, done);
  });

  it('Change password - old password mismatch', function(done) {
    testSession.post('/auth/password')
      .send({old: 'wrong-pwd', new: 'new-pwd'})
      .expect(http.BAD_REQUEST, done);
  });

  it('Change password - success', function(done) {
    testSession.post('/auth/password')
      .send({old: 'qwerasdf', new: 'new-pwd'})
      .expect(http.NO_CONTENT, done);
  });
});