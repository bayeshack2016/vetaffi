package models.daos

import java.util.UUID
import javax.inject.Inject

import models.UserValues
import play.api.libs.json.Json
import play.modules.reactivemongo.ReactiveMongoApi
import play.modules.reactivemongo.json._
import reactivemongo.api.commands.WriteResult
import reactivemongo.play.json.collection.JSONCollection

import scala.concurrent.ExecutionContext.Implicits.global
import scala.concurrent.Future

class UserValuesDAOImpl @Inject()(val reactiveMongoApi: ReactiveMongoApi) extends UserValuesDAO {

  def collection: Future[JSONCollection] = reactiveMongoApi.database.map(_.collection("user_values"))

  /**
    * Finds user values for a user by their userID.
    *
    * @param userID The ID of the user to find values for.
    * @return The found user values or None if no user for the given ID could be found.
    */
  override def find(userID: UUID): Future[Option[UserValues]] = {
    collection.flatMap {
      _.find(Json.obj("userID" -> userID.toString)).one[UserValues]
    }
  }

  /**
    * Update the [String, String] map of user values.
    *
    * @param values New user values, will overwrite existing values of the same key.
    */
  override def update(userID: UUID, values: UserValues): Future[WriteResult] = {
    collection.flatMap((userValuesCollection: JSONCollection) => {

      val userValuesOptionFuture: Future[Option[UserValues]] =
        userValuesCollection.find(Json.obj("userID" -> values.userID.toString)).one[UserValues]

      val existingValuesFuture: Future[Map[String, String]] = userValuesOptionFuture.map {
        case userValues if userValues.nonEmpty => userValues.get.values
        case _ => Map()
      }

      existingValuesFuture.flatMap((existingValues: Map[String, String]) => {
        userValuesCollection.update(
          Json.obj("userID" -> values.userID.toString),
          // The values on the RHS of `++` will overwrite the values of the LHS
          Json.obj("$set" -> Json.obj("values" -> Json.toJson(values.values ++ existingValues))),
          upsert = true)
      })
    })
  }
}
