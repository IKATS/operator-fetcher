pipeline {
    options { 
        buildDiscarder(logRotator(numToKeepStr: '4', artifactNumToKeepStr: '5'))
        disableConcurrentBuilds() 
    }
    agent any

    stages {
        stage('Fetch SCM') {
            steps {
                checkout scm
            }
        }
        stage('Build and push image') {
            agent { node { label 'docker' } }
            steps {
                script {
                    dockerBuild 'hub.ops.ikats.org/operator-fetcher'
                }
            }
        }
    }
}
